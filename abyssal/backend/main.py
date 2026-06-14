import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Abyssal API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from abyssal.api.router import router
from abyssal.crawler.db import init_db
from abyssal.wayback.db import init_wayback_db
from abyssal.crawler.scheduler import start_scheduler

app.include_router(router)


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
    try:
        start_scheduler()
        logger.info("Auto-recrawl scheduler started")
    except Exception as e:
        logger.warning("Could not start scheduler: %s", e)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
