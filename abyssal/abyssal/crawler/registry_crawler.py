"""
Registry Address Book Crawler.

Fetches hosts.txt from known I2P registry sites (reg.i2p, notbob.i2p, stats.i2p,
inr.i2p, etc.), parses hostname=b32address entries, and adds them to the
site_status table so they appear in the public address book.

Periodically runs in the background. Also auto-discovers new registry sources
by looking for sites that serve hosts.txt files or contain links to them.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from abyssal.config import I2PD_HTTP_PROXY
from abyssal.crawler.db import get_db, upsert_site_status

logger = logging.getLogger(__name__)

# Seed registries — hardcoded initially, grows as crawler discovers more.
# Format: URL to hosts.txt (or root page that links to one).
SEED_REGISTRIES = [
    "http://reg.i2p/hosts.txt",
    "http://notbob.i2p/hosts.txt",
    "http://stats.i2p/hosts.txt",
    "http://inr.i2p/hosts.txt",
    "http://inr.i2p/contacts/",
    "http://i2pd.i2p/hosts.txt",
]

CHECK_INTERVAL = 6 * 3600  # every 6 hours
INITIAL_DELAY = 60  # wait 60s after startup for i2pd to warm up


async def _init_registry_db():
    """Ensure the registry_sources table exists."""
    db = await get_db()
    try:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS registry_sources (
                url TEXT PRIMARY KEY,
                discovered_at TEXT DEFAULT (datetime('now')),
                last_fetched TEXT,
                entries_found INTEGER DEFAULT 0,
                active INTEGER DEFAULT 1
            )
        """)
        await db.commit()
    finally:
        await db.close()


async def _seed_registries():
    """Insert the hardcoded seed registries if the table is empty."""
    db = await get_db()
    try:
        existing = await db.execute_fetchall("SELECT COUNT(*) AS n FROM registry_sources")
        if existing and existing[0]["n"] > 0:
            return
        for url in SEED_REGISTRIES:
            await db.execute(
                "INSERT OR IGNORE INTO registry_sources (url) VALUES (?)",
                (url,),
            )
        await db.commit()
        logger.info("Seeded %d registry source(s)", len(SEED_REGISTRIES))
    finally:
        await db.close()


async def _fetch_hosts_txt(url: str) -> Optional[str]:
    """Fetch a hosts.txt file (or any text content) from an I2P URL."""
    try:
        async with httpx.AsyncClient(proxy=I2PD_HTTP_PROXY, timeout=60.0) as client:
            resp = await client.get(url, headers={"User-Agent": "Abyssal-Registry-Crawler/1.0"})
            if resp.status_code == 200 and resp.text:
                return resp.text
    except Exception as e:
        logger.debug("Registry fetch failed for %s: %s", url, e)
    return None


def _parse_hosts_line(line: str) -> Optional[tuple[str, str, str]]:
    """Parse a hosts.txt line into (hostname, b32, address_helper).

    Handles formats:
      hostname=b32address.b32.i2p
      hostname=base64~destination==
    """
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        return None
    hostname, _, value = line.partition("=")
    hostname = hostname.strip().lower()
    value = value.strip()
    if not hostname.endswith(".i2p"):
        return None
    if value.endswith(".b32.i2p"):
        b32 = value[:-9]
        return (hostname, b32, "")
    if value and "~" in value:
        try:
            import base64, hashlib
            raw = base64.b64decode(value.replace("~", "=").replace("-", "+").replace("_", "/"))
            b32 = base64.b32encode(hashlib.sha256(raw).digest()).decode().lower().replace("=", "")
            return (hostname, b32, value)
        except Exception:
            pass
    return None


async def _process_registry(url: str) -> int:
    """Fetch a registry URL, parse entries, upsert into site_status. Returns count of new entries."""
    logger.info("Fetching registry: %s", url)
    content = await _fetch_hosts_txt(url)
    if not content:
        return 0
    count = 0
    for line in content.split("\n"):
        parsed = _parse_hosts_line(line)
        if not parsed:
            continue
        hostname, b32, helper = parsed
        try:
            await upsert_site_status(
                hostname=hostname,
                online=False,
                b32=b32,
                address_helper=helper,
                status_code=0,  # registry entry, not directly checked
            )
            count += 1
        except Exception as e:
            logger.debug("Failed to upsert %s: %s", hostname, e)
    logger.info("Registry %s: %d entries processed", url, count)
    return count


async def _discover_new_registries():
    """Look in site_status for potential new registry hosts (contain 'hosts.txt' or known patterns)."""
    db = await get_db()
    try:
        known = await db.execute_fetchall("SELECT url FROM registry_sources")
        known_urls = {r["url"] for r in known}

        patterns_to_check = [
            "http://reg.i2p",
            "http://inr.i2p",
            "http://notbob.i2p",
            "http://stats.i2p",
            "http://i2pd.i2p",
        ]
        discovered = []
        for base in patterns_to_check:
            candidates = [
                f"{base}/hosts.txt",
                f"{base}/addressbook",
                f"{base}/contacts/",
            ]
            for url in candidates:
                if url not in known_urls:
                    discovered.append(url)
        if discovered:
            for url in discovered:
                await db.execute(
                    "INSERT OR IGNORE INTO registry_sources (url) VALUES (?)",
                    (url,),
                )
            await db.commit()
            logger.info("Discovered %d new registry candidate(s)", len(discovered))

        pages_with_links = await db.execute_fetchall(
            "SELECT DISTINCT url FROM crawled_pages WHERE url LIKE '%hosts.txt%' OR url LIKE '%addressbook%' OR url LIKE '%registry%' LIMIT 20"
        )
        for row in pages_with_links:
            url = row["url"]
            if url not in known_urls:
                await db.execute(
                    "INSERT OR IGNORE INTO registry_sources (url) VALUES (?)",
                    (url,),
                )
                logger.info("Discovered registry from crawled pages: %s", url)
        await db.commit()
    finally:
        await db.close()


async def _update_registry_meta(url: str, count: int):
    """Update the last_fetched and entries_found for a registry source."""
    db = await get_db()
    try:
        now = datetime.now(timezone.utc).isoformat()
        await db.execute(
            "UPDATE registry_sources SET last_fetched = ?, entries_found = ? WHERE url = ?",
            (now, count, url),
        )
        await db.commit()
    finally:
        await db.close()


async def registry_crawl_loop():
    """Main loop: fetch all active registries, discover new ones, repeat."""
    await _init_registry_db()
    await _seed_registries()

    await asyncio.sleep(INITIAL_DELAY)

    while True:
        try:
            db = await get_db()
            try:
                registries = await db.execute_fetchall(
                    "SELECT url FROM registry_sources WHERE active = 1 ORDER BY url"
                )
            finally:
                await db.close()

            if registries:
                logger.info("Registry crawl: %d source(s) to fetch", len(registries))
                for row in registries:
                    url = row["url"]
                    count = await _process_registry(url)
                    await _update_registry_meta(url, count)

            await _discover_new_registries()
        except Exception as e:
            logger.error("Registry crawl error: %s", e, exc_info=True)

        await asyncio.sleep(CHECK_INTERVAL)
