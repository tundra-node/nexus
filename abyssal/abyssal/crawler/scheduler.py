"""
Auto-recrawl scheduler.

Every CHECK_INTERVAL seconds:
1. Finds sites whose last_crawled + interval has passed → marks them "scheduled" (recrawl_at)
2. Finds sites whose recrawl_at has passed → starts a crawl job (respects active-job guard)

Uses per-status recrawl intervals:
- 200 OK        → 24h
- 429            → 72h  (rate-limited)
- 400-499        → 72h  (blocked)
- 500+ / offline → 168h (7d, server error or connection failure)
"""

import asyncio
import logging
import random
from datetime import datetime, timezone, timedelta
from typing import Optional

from . import db
from .worker import crawl_job

logger = logging.getLogger(__name__)

CHECK_INTERVAL      = 5 * 60    # wake up every 5 minutes
MAX_JITTER_SECS     = 60 * 60   # spread recrawls over up to 1 hour

_running   = False
_loop_task: Optional[asyncio.Task] = None


# ── Main loop ──────────────────────────────────────────────────────────────────

async def _recrawl_loop() -> None:
    global _running
    _running = True
    while _running:
        await asyncio.sleep(CHECK_INTERVAL)
        try:
            await _tick()
        except Exception as exc:
            logger.error("Scheduler tick error: %s", exc, exc_info=True)


async def _tick() -> None:
    # Step 1: Schedule due sites for future recrawl
    due = await db.get_auto_crawl_sites()
    if due:
        logger.info("Scheduler: %d site(s) due for recrawl", len(due))
        for hostname, interval_hours in due:
            if await db.get_active_job_for_hostname(hostname) is not None:
                continue
            # Randomize jitter: spread recrawls across the full interval
            # e.g. for 24h interval, jitter between 0 and 20 hours
            max_jitter = min(interval_hours * 3600, 20 * 3600)  # cap at 20 hours
            jitter = random.uniform(0, max_jitter)
            scheduled_at = (datetime.now(timezone.utc) + timedelta(seconds=jitter)).isoformat()
            await db.set_recrawl_at(hostname, scheduled_at)
            logger.debug("Scheduled %s for recrawl at %s", hostname, scheduled_at)

    # Step 2: Start crawls for scheduled sites whose time has come
    scheduled = await db.get_scheduled_sites()
    if scheduled:
        for site in scheduled:
            hostname = site["hostname"]
            if await db.get_active_job_for_hostname(hostname) is not None:
                await db.clear_recrawl_at(hostname)
                continue
            await db.clear_recrawl_at(hostname)
            job_id = await db.create_job(
                f"http://{hostname}",
                max_pages=0,
                max_depth=5,
                concurrency=10,
                delay_seconds=random.uniform(0.5, 3.0),
            )
            asyncio.create_task(crawl_job(job_id))
            logger.info("Recrawl: job %d started for %s", job_id, hostname)


# ── Public API ─────────────────────────────────────────────────────────────────

def start_scheduler() -> None:
    global _loop_task
    if _loop_task is not None and not _loop_task.done():
        return
    _loop_task = asyncio.create_task(_recrawl_loop())
    logger.info(
        "Auto-recrawl scheduler started "
        "(check every %ds, jitter up to %ds)",
        CHECK_INTERVAL, MAX_JITTER_SECS,
    )


def stop_scheduler() -> None:
    global _running, _loop_task
    _running = False
    if _loop_task:
        _loop_task.cancel()
        _loop_task = None
