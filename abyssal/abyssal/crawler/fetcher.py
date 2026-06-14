import asyncio
import logging
import random
import re
import time
from typing import Optional
from urllib.parse import urlparse, urlunparse

import httpx

from abyssal.config import I2PD_HTTP_PROXY

logger = logging.getLogger(__name__)

TRANSIENT_HTTP_CODES = {502, 503, 504, 429}
MAX_RETRIES = 3
BASE_RETRY_DELAY = 1.0
ROBOTS_CACHE_TTL = 86400


class FetchResult:
    __slots__ = ("success", "status_code", "response", "error", "retryable", "retry_after")

    def __init__(
        self,
        success: bool = False,
        status_code: int = 0,
        response: Optional[httpx.Response] = None,
        error: str = "",
        retryable: bool = False,
        retry_after: float = 0.0,
    ):
        self.success = success
        self.status_code = status_code
        self.response = response
        self.error = error
        self.retryable = retryable
        self.retry_after = retry_after


def normalize_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        hostname = parsed.netloc.lower()
        if (scheme == "http" and hostname.endswith(":80")) or \
           (scheme == "https" and hostname.endswith(":443")):
            hostname = hostname.rsplit(":", 1)[0]
        path = parsed.path.lower() or "/"
        end_slash = path.endswith("/") and len(path) > 1
        path = re.sub(r"/{2,}", "/", path)
        parts = []
        for part in path.split("/"):
            if part in ("", "."):
                continue
            if part == "..":
                if parts:
                    parts.pop()
            else:
                parts.append(part)
        path = "/" + "/".join(parts)
        if parts and end_slash:
            path += "/"
        query = parsed.query
        if query:
            params = sorted(query.split("&"))
            query = "&".join(params)
        norm = urlunparse((scheme, hostname, path, parsed.params, query, ""))
        return norm
    except Exception:
        return url


class PageFetcher:
    def __init__(self, proxy: str = I2PD_HTTP_PROXY, timeout: float = 120.0):
        self.proxy = proxy
        self.timeout = timeout
        self._last_req: dict[str, float] = {}
        self._retry_after: dict[str, float] = {}
        self._robots: dict[str, tuple[list[str], float, float]] = {}

    async def _fetch_robots(self, client: httpx.AsyncClient, hostname: str) -> tuple[list[str], float]:
        base = f"http://{hostname}"
        disallowed: list[str] = []
        crawl_delay = 0.0
        try:
            resp = await client.get(
                f"{base}/robots.txt", timeout=30.0,
                headers={"User-Agent": "Abyssal-Crawler/1.0"},
            )
            if resp.status_code == 200:
                current_agent: Optional[str] = None
                for line in resp.text.splitlines():
                    line = line.strip()
                    lc = line.lower()
                    if lc.startswith("user-agent:"):
                        agent = line.split(":", 1)[1].strip()
                        current_agent = agent if agent in ("*", "Abyssal-Crawler", "Abyssal-Crawler/1.0") else None
                    elif current_agent and lc.startswith("disallow:"):
                        path = line.split(":", 1)[1].strip()
                        if path:
                            disallowed.append(base.rstrip("/") + path)
                    elif current_agent and lc.startswith("crawl-delay:"):
                        try:
                            crawl_delay = float(line.split(":", 1)[1].strip())
                        except ValueError:
                            pass
        except Exception as e:
            logger.debug("Failed to fetch robots.txt for %s: %s", hostname, e)
        return disallowed, crawl_delay

    async def _check_robots(self, client: httpx.AsyncClient, hostname: str) -> tuple[bool, float]:
        now = time.monotonic()
        if hostname in self._robots:
            disallowed, crawl_delay, fetched_at = self._robots[hostname]
            if now - fetched_at < ROBOTS_CACHE_TTL:
                return True, crawl_delay
        disallowed, crawl_delay = await self._fetch_robots(client, hostname)
        self._robots[hostname] = (disallowed, crawl_delay, now)
        return True, crawl_delay

    async def fetch(
        self,
        url: str,
        client: httpx.AsyncClient,
        domain_min_delay: float = 1.0,
        user_agent: str = "Abyssal-Crawler/1.0",
    ) -> FetchResult:
        hostname = urlparse(url).netloc

        # Respect retry-after backoff
        now = time.monotonic()
        if hostname in self._retry_after and now < self._retry_after[hostname]:
            wait = self._retry_after[hostname] - now
            logger.info("Domain %s is rate-limited, waiting %.1fs", hostname, wait)
            await asyncio.sleep(wait)

        # Robots check
        _, robots_delay = await self._check_robots(client, hostname)
        effective_delay = max(domain_min_delay, robots_delay)

        # Per-domain minimum interval
        last = self._last_req.get(hostname, 0.0)
        wait = effective_delay - (now - last)
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_req[hostname] = time.monotonic()

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = await client.get(url, headers={"User-Agent": user_agent})

                if resp.status_code == 429:
                    ra = resp.headers.get("Retry-After", "30")
                    try:
                        retry_seconds = float(ra)
                    except ValueError:
                        retry_seconds = 30.0
                    self._retry_after[hostname] = time.monotonic() + retry_seconds
                    if attempt < MAX_RETRIES:
                        await asyncio.sleep(retry_seconds)
                        continue
                    return FetchResult(
                        success=False, status_code=429, error="Rate limited",
                        retryable=True, retry_after=retry_seconds,
                    )

                if resp.status_code in TRANSIENT_HTTP_CODES:
                    if attempt < MAX_RETRIES:
                        sleep = BASE_RETRY_DELAY * (2 ** (attempt - 1)) * random.uniform(0.5, 1.5)
                        logger.info("Retrying %s in %.1fs (HTTP %d, attempt %d/%d)", url, sleep, resp.status_code, attempt, MAX_RETRIES)
                        await asyncio.sleep(sleep)
                        continue
                    return FetchResult(
                        success=False, status_code=resp.status_code,
                        error=f"HTTP {resp.status_code} after {MAX_RETRIES} attempts",
                        retryable=True,
                    )

                if resp.status_code < 400:
                    return FetchResult(success=True, status_code=resp.status_code, response=resp)

                return FetchResult(
                    success=False, status_code=resp.status_code,
                    error=f"HTTP {resp.status_code}", retryable=False,
                )

            except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as e:
                if attempt < MAX_RETRIES:
                    sleep = BASE_RETRY_DELAY * (2 ** (attempt - 1)) * random.uniform(0.5, 1.5)
                    logger.info("Retrying %s in %.1fs (network error: %s)", url, sleep, e)
                    await asyncio.sleep(sleep)
                    continue
                return FetchResult(success=False, error=f"Network error: {e}", retryable=True)

            except Exception as e:
                logger.error("Unexpected error fetching %s: %s", url, e)
                return FetchResult(success=False, error=str(e), retryable=False)

        return FetchResult(success=False, error="Max retries exceeded", retryable=True)
