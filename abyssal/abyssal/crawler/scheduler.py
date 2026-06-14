import asyncio
import logging
from typing import Optional

from . import db
from .worker import crawl_job

logger = logging.getLogger(__name__)

CHECK_INTERVAL = 3600
RECRAWL_AFTER = 86400

_running = False
_loop_task: Optional[asyncio.Task] = None


async def _recrawl_loop():
    global _running
    _running = True
    while _running:
        try:
            due = await db.get_auto_crawl_sites()
            for hostname in due:
                if not _running:
                    break
                url = f"http://{hostname}"
                logger.info("Auto-recrawl: starting unlimited crawl for %s", url)
                job_id = await db.create_job(url, max_pages=0, max_depth=5)
                asyncio.create_task(crawl_job(job_id))
                await asyncio.sleep(30)
        except Exception as e:
            logger.error("Auto-recrawl loop error: %s", e)

        for _ in range(CHECK_INTERVAL):
            if not _running:
                break
            await asyncio.sleep(1)


def start_scheduler():
    global _loop_task
    if _loop_task is not None and not _loop_task.done():
        return
    _loop_task = asyncio.create_task(_recrawl_loop())


def stop_scheduler():
    global _running, _loop_task
    _running = False
    if _loop_task:
        _loop_task.cancel()
        _loop_task = None
