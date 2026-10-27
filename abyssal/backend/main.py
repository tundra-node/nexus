import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Abyssal API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

from abyssal.api.router import router
from abyssal.crawler.db import init_db, create_job, get_jobs, get_db as get_crawler_db
from abyssal.crawler.worker import crawl_job
from abyssal.wayback.db import init_wayback_db
from abyssal.crawler.scheduler import start_scheduler
from abyssal.resolver.resolver import resolve_host
from abyssal.seeds import SEED_URLS, SEED_MAX_PAGES, SEED_MAX_DEPTH, SEED_CONCURRENCY, SEED_DELAY
from abyssal.config import (
    AUTOSEED_ENABLED,
    REGISTRY_CRAWLER_ENABLED,
    SCHEDULER_ENABLED,
)

# Seconds to wait after startup before seeding, to give i2pd time to bootstrap.
# Only runs on a genuinely fresh database (zero jobs). Has no effect on restarts.
_SEED_DELAY_SECS = 120

app.include_router(router)


async def _resume_orphaned_jobs():
    """Reset orphaned 'running' jobs to 'pending' so workers can pick them up."""
    try:
        db = await get_crawler_db()
        orphans = await db.execute_fetchall(
            "SELECT id FROM crawl_jobs WHERE status = 'running'"
        )
        if orphans:
            await db.execute("UPDATE crawl_jobs SET status = 'pending' WHERE status = 'running'")
            await db.commit()
            logger.info("Reset %d orphaned running jobs to pending", len(orphans))
            for row in orphans:
                asyncio.create_task(crawl_job(row["id"]))
                await asyncio.sleep(0.2)
        await db.close()
    except Exception as e:
        logger.warning("Could not resume orphaned jobs: %s", e)


async def _seed_if_fresh():
    """
    Seed the crawler with the configured SEED_URLS — but ONLY on a completely
    fresh database (no jobs of any kind exist).  Every subsequent restart is a
    no-op, regardless of job statuses.  If seeds fail because i2pd wasn't ready
    yet, rerun them manually from the Admin UI.
    """
    await asyncio.sleep(_SEED_DELAY_SECS)

    existing = await get_jobs()
    if existing["jobs"]:
        logger.info(
            "Database already has %d job(s) — skipping seed (not a fresh DB)",
            existing["total"],
        )
        return

    logger.info("Fresh database — seeding %d crawl job(s) after %ds delay",
                len(SEED_URLS), _SEED_DELAY_SECS)
    for url in SEED_URLS:
        job_id = await create_job(
            url,
            max_pages=SEED_MAX_PAGES,
            max_depth=SEED_MAX_DEPTH,
            concurrency=SEED_CONCURRENCY,
            delay_seconds=SEED_DELAY,
        )
        asyncio.create_task(crawl_job(job_id))
        logger.info("Seeded job %d → %s", job_id, url)


@app.on_event("startup")
async def startup():
    try:
        await init_db()
        logger.info("Crawler database initialized")
    except Exception as e:
        logger.warning("Could not init crawler DB: %s", e)

    try:
        await init_wayback_db()
        logger.info("Wayback database initialized")
    except Exception as e:
        logger.warning("Could not init wayback DB: %s", e)

    # Resume any orphaned jobs before seeding
    if AUTOSEED_ENABLED:
        await _resume_orphaned_jobs()
    else:
        logger.info("AUTOSEED_ENABLED is off — not resuming orphaned jobs")

    # Background task — does not block startup or nginx
    if AUTOSEED_ENABLED:
        asyncio.create_task(_seed_if_fresh())
    else:
        logger.info("AUTOSEED_ENABLED is off — skipping seed crawls")

    if SCHEDULER_ENABLED:
        try:
            start_scheduler()
            logger.info("Auto-recrawl scheduler started")
        except Exception as e:
            logger.warning("Could not start scheduler: %s", e)
    else:
        logger.info("SCHEDULER_ENABLED is off — no automatic recrawls")

    if REGISTRY_CRAWLER_ENABLED:
        asyncio.create_task(_resolve_incomplete_hosts())

        try:
            from abyssal.crawler.registry_crawler import registry_crawl_loop
            asyncio.create_task(registry_crawl_loop())
            logger.info("Registry address book crawler started")
        except Exception as e:
            logger.warning("Could not start registry crawler: %s", e)
    else:
        logger.info("REGISTRY_CRAWLER_ENABLED is off — no registry crawling")


async def _resolve_incomplete_hosts():
    """Periodically find hosts without b32 addresses and resolve them."""
    await asyncio.sleep(300)  # wait 5 min after startup
    while True:
        try:
            db = await get_crawler_db()
            rows = await db.execute_fetchall(
                "SELECT hostname FROM site_status WHERE (b32 IS NULL OR b32 = '') AND hostname LIKE '%.i2p'"
            )
            await db.close()
            if rows:
                logger.info("Address resolver: %d unresolved host(s) found", len(rows))
                for row in rows:
                    hostname = row["hostname"]
                    result = await resolve_host(hostname)
                    if result:
                        db2 = await get_crawler_db()
                        await db2.execute(
                            "UPDATE site_status SET b32 = ?, address_helper = ? WHERE hostname = ?",
                            (result["b32"], result["address_helper"], hostname),
                        )
                        await db2.commit()
                        await db2.close()
                        logger.info("Resolved %s → %s", hostname, result["b32"][:20])
                    await asyncio.sleep(5)  # rate limit between resolves
        except Exception as e:
            logger.warning("Address resolver error: %s", e)
        await asyncio.sleep(3600)  # check every hour


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
