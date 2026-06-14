import asyncio
import logging
import random
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from abyssal.config import I2PD_HTTP_PROXY

from . import db
from .fetcher import PageFetcher, normalize_url
from .extractor import extract_links, extract_title, extract_meta, extract_canonical
from ..classifier.classify import analyze_page
from ..resolver.resolver import resolve_host
from ..wayback import storage as wb_storage
from ..wayback import db as wb_db

logger = logging.getLogger(__name__)

_active_jobs: set[int] = set()
_resolved_cache: dict[str, dict] = {}


async def _resolve_hostname(hostname: str) -> tuple[str, str]:
    if hostname in _resolved_cache:
        result = _resolved_cache[hostname]
        return result["b32"], result["address_helper"]
    result = await resolve_host(hostname)
    if result:
        _resolved_cache[hostname] = result
        return result["b32"], result["address_helper"]
    return "", ""


async def _process_url(
    client: httpx.AsyncClient,
    fetcher: PageFetcher,
    job_id: int,
    url: str,
    depth: int,
    start_hostname: str,
):
    hostname = urlparse(url).netloc
    logger.info("Processing job=%d: %s (depth=%d)", job_id, url, depth)

    fetch_result = await fetcher.fetch(url, client)
    if not fetch_result.success:
        if fetch_result.retryable:
            await db.enqueue_urls(job_id, [(url, depth)])
            logger.info("Re-enqueued %s for retry (%s)", url, fetch_result.error)
        else:
            logger.warning("Skipping %s (%s)", url, fetch_result.error)
        await db.upsert_site_status(hostname, online=False)
        return

    resp = fetch_result.response
    content_type = resp.headers.get("content-type", "")
    online = resp.status_code < 400

    title = ""
    links: list[str] = []
    meta: dict = {}

    if "text/html" in content_type:
        body = resp.text
        title = extract_title(body)
        links = extract_links(body, url)
        meta = analyze_page(body, url)

    b32 = ""
    address_helper = ""
    if hostname.endswith(".i2p") and ":" not in hostname:
        b32, address_helper = await _resolve_hostname(hostname)

    canonical = ""
    if "text/html" in content_type:
        soup = BeautifulSoup(resp.text, "html.parser")
        canonical = extract_canonical(soup, url)
        extra_meta = extract_meta(soup)
        meta["description"] = meta.get("description") or extra_meta.get("description", "")
        meta["keywords"] = meta.get("keywords") or extra_meta.get("keywords", "")

    await db.save_page(
        job_id=job_id,
        url=url,
        title=title,
        content=resp.text if "text/html" in content_type else "",
        status_code=resp.status_code,
        depth=depth,
        b32=b32,
        address_helper=address_helper,
        **{k: v for k, v in meta.items() if k in ("language", "site_type", "description", "keywords")},
    )

    await db.upsert_site_status(hostname, online=True, b32=b32, address_helper=address_helper)
    await db.inc_job_pages(job_id)

    # Wayback snapshot (HTML only)
    if "text/html" in content_type and resp.text:
        try:
            snap_meta = wb_storage.store_snapshot(
                url=url, content=resp.text,
                status_code=resp.status_code, content_type=content_type,
            )
            await wb_db.add_snapshot(
                url=url, snapshot_time=snap_meta["snapshot_time"],
                title=title, status_code=resp.status_code,
                content_type=content_type, file_path=snap_meta["file_path"],
                size_bytes=snap_meta["size_bytes"], job_id=job_id,
            )
            if title:
                await wb_db.upsert_tracked_url(url, title=title)
        except Exception as wb_err:
            logger.debug("Wayback snapshot skipped for %s: %s", url, wb_err)

    # Process links
    same_host_links: list[tuple[str, int]] = []
    seen_new_hosts: set[str] = set()
    for link in links:
        link_host = urlparse(link).netloc
        if ".i2p" not in link_host:
            continue
        if link_host == hostname or link_host == start_hostname:
            same_host_links.append((link, depth + 1))
        else:
            await db.record_site_link(start_hostname, link_host)
            if link_host not in seen_new_hosts:
                seen_new_hosts.add(link_host)
                existing = await db.get_job_for_hostname(link_host)
                if existing is None:
                    new_job_id = await db.create_job(
                        f"http://{link_host}", max_pages=0, max_depth=5, spawned_by=job_id,
                    )
                    logger.info("Auto-spawned unlimited job %d for %s", new_job_id, link_host)
                    asyncio.create_task(crawl_job(new_job_id))

    if same_host_links:
        await db.enqueue_urls(job_id, same_host_links)


async def crawl_job(job_id: int):
    if job_id in _active_jobs:
        logger.info("crawl_job(%d): already active, skipping", job_id)
        return
    _active_jobs.add(job_id)

    fetcher = PageFetcher(proxy=I2PD_HTTP_PROXY, timeout=120.0)

    try:
        job = await db.get_job(job_id)
        if not job:
            logger.warning("crawl_job(%d): job not found", job_id)
            return
        if job["status"] in ("paused", "completed", "failed"):
            return

        await db.update_job(job_id, status="running")
        max_pages = job["max_pages"]
        unlimited = max_pages <= 0
        max_depth = job["max_depth"]
        concurrency = max(1, job.get("concurrency", 3) or 3)
        delay = max(0.0, job.get("delay_seconds", 2.0) or 2.0)
        start_hostname = urlparse(job["url"]).netloc

        semaphore = asyncio.Semaphore(concurrency)
        pending: set[asyncio.Task] = set()

        async with httpx.AsyncClient(
            proxy=I2PD_HTTP_PROXY, timeout=120.0, follow_redirects=True,
        ) as client:
            while job_id in _active_jobs:
                current = await db.get_job(job_id)
                if current and current["status"] == "paused":
                    break

                if not unlimited:
                    pages = await db.get_job_pages_crawled(job_id)
                    if pages >= max_pages:
                        break

                item = await db.get_next_queue_item(job_id)
                if not item:
                    if pending:
                        await asyncio.sleep(1)
                        continue
                    break

                raw_url = item["url"]
                url = normalize_url(raw_url)
                depth = item["depth"]

                if depth > max_depth:
                    continue

                exists = await db.page_exists_in_job(job_id, url)
                if exists:
                    continue

                async def _run(url=url, depth=depth):
                    async with semaphore:
                        await _process_url(client, fetcher, job_id, url, depth, start_hostname)
                    if delay > 0:
                        await asyncio.sleep(delay * random.uniform(0.5, 1.5))

                task = asyncio.create_task(_run())
                pending.add(task)
                task.add_done_callback(pending.discard)

            # Wait for remaining tasks BEFORE client closes
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)

        current = await db.get_job(job_id)
        if current and current["status"] != "paused":
            await db.update_job(job_id, status="completed",
                                finished_at=datetime.now(timezone.utc).isoformat())

    except Exception as e:
        logger.error("Crawl job %d failed: %s", job_id, e, exc_info=True)
        await db.update_job(job_id, status="failed")
    finally:
        _active_jobs.discard(job_id)


def cancel_job(job_id: int):
    _active_jobs.discard(job_id)
