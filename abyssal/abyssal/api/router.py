import asyncio
import logging
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Header, Query
from pydantic import BaseModel

from abyssal.config import API_KEY
from abyssal.crawler import db as crawler_db
from abyssal.crawler.worker import crawl_job, cancel_job
from abyssal.db import search as search_db
from abyssal.wayback import db as wb_db
from abyssal.wayback import storage as wb_storage
from abyssal.wayback.rewrite import rewrite_external_urls, inline_css
from abyssal.config import I2PD_HTTP_PROXY

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/abyssal", tags=["abyssal"])


# Keep private admin endpoints behind api-key.
# All read-only endpoints (search, directory, wayback viewing) are public.


async def require_admin(api_key: str = Header("")):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")


# ── Search (public) ────────────────────────────────────────────


class SearchResult(BaseModel):
    q: str
    language: str = ""
    site_type: str = ""
    page: int = 1
    per_page: int = 20


@router.get("/search")
async def search(
    q: str = Query(""),
    language: str = Query(""),
    site_type: str = Query(""),
    page: int = Query(1),
    per_page: int = Query(20),
):
    if not q:
        return {"results": [], "total": 0, "page": 1, "per_page": per_page, "total_pages": 0}
    return await search_db.search_pages(q, language, site_type, page, per_page)


@router.get("/facets")
async def facets():
    return await search_db.get_facets()


# ── Directory / Sites (public) ─────────────────────────────────


@router.get("/sites")
async def list_sites(
    language: str = Query(""),
    site_type: str = Query(""),
    online: Optional[bool] = Query(None),
    page: int = Query(1),
    per_page: int = Query(50),
):
    return await search_db.get_sites(language, site_type, online, page, per_page)


@router.get("/sites/{hostname}")
async def get_site(hostname: str):
    site = await search_db.get_site(hostname)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


@router.get("/site-status")
async def site_status():
    return await crawler_db.get_site_status()


@router.get("/graph")
async def graph():
    return await crawler_db.get_graph_data()


# ── Crawler Admin (private) ────────────────────────────────────


class StartCrawlRequest(BaseModel):
    url: str
    max_pages: int = 0
    max_depth: int = 5
    concurrency: int = 3
    delay_seconds: float = 2.0


@router.post("/crawl/start")
async def start_crawl(req: StartCrawlRequest, api_key: str = Header("")):
    await require_admin(api_key)
    if not req.url:
        raise HTTPException(status_code=400, detail="url is required")
    parsed = urlparse(req.url)
    if not parsed.scheme:
        req.url = "http://" + req.url
    job_id = await crawler_db.create_job(
        req.url, req.max_pages, req.max_depth, req.concurrency, req.delay_seconds,
    )
    asyncio.create_task(crawl_job(job_id))
    return {"job_id": job_id}


@router.get("/crawl/jobs")
async def list_jobs(api_key: str = Header("")):
    await require_admin(api_key)
    return await crawler_db.get_jobs()


@router.get("/crawl/jobs/{job_id}")
async def get_job(job_id: int, api_key: str = Header("")):
    await require_admin(api_key)
    job = await crawler_db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.delete("/crawl/jobs/{job_id}")
async def delete_job(job_id: int, api_key: str = Header("")):
    await require_admin(api_key)
    cancel_job(job_id)
    await crawler_db.delete_job(job_id)
    return {"status": "deleted"}


@router.post("/crawl/jobs/{job_id}/pause")
async def pause_job(job_id: int, api_key: str = Header("")):
    await require_admin(api_key)
    await crawler_db.update_job(job_id, status="paused")
    return {"status": "paused"}


@router.post("/crawl/jobs/{job_id}/resume")
async def resume_job(job_id: int, api_key: str = Header("")):
    await require_admin(api_key)
    await crawler_db.update_job(job_id, status="pending")
    asyncio.create_task(crawl_job(job_id))
    return {"status": "resumed"}


@router.post("/crawl/jobs/{job_id}/rerun")
async def rerun_job(job_id: int, api_key: str = Header("")):
    await require_admin(api_key)
    original = await crawler_db.get_job(job_id)
    if not original:
        raise HTTPException(status_code=404, detail="Job not found")
    new_id = await crawler_db.create_job(
        original["url"], original["max_pages"], original["max_depth"],
        original.get("concurrency", 3), original.get("delay_seconds", 2.0),
    )
    asyncio.create_task(crawl_job(new_id))
    return {"job_id": new_id}


# ── Wayback Machine (public read, private write) ──────────────


@router.get("/wayback/stats")
async def wayback_stats():
    return await wb_db.get_stats()


@router.get("/wayback/urls")
async def wayback_urls():
    return await wb_db.get_all_tracked_urls()


@router.get("/wayback/snapshots")
async def wayback_snapshots(
    url: str = Query(""),
    limit: int = Query(500),
    offset: int = Query(0),
):
    if not url:
        return {"snapshots": [], "total": 0}
    snapshots = await wb_db.get_snapshots_for_url(url, limit, offset)
    total = await wb_db.count_snapshots_for_url(url)
    return {"snapshots": snapshots, "total": total}


@router.get("/wayback/snapshots/{snapshot_id}")
async def get_snapshot(snapshot_id: int):
    snap = await wb_db.get_snapshot(snapshot_id)
    if not snap:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return snap


@router.get("/wayback/snapshots/{snapshot_id}/view")
async def view_snapshot(snapshot_id: int, raw: bool = Query(False)):
    snap = await wb_db.get_snapshot(snapshot_id)
    if not snap:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    content = wb_storage.load_snapshot(snap["file_path"])
    if content is None:
        raise HTTPException(status_code=404, detail="Snapshot file not found on disk")
    if raw:
        return {"content": content, "url": snap["url"]}
    rewritten = rewrite_external_urls(content, snap["url"])
    return {"content": rewritten, "url": snap["url"]}


@router.get("/wayback/search")
async def wayback_search(q: str = Query(""), limit: int = Query(50), offset: int = Query(0)):
    if not q:
        return []
    return await wb_db.search_snapshots(q, limit, offset)


@router.post("/wayback/capture")
async def capture_snapshot(url: str = Query(""), api_key: str = Header("")):
    await require_admin(api_key)
    if not url:
        raise HTTPException(status_code=400, detail="url is required")
    import httpx
    async with httpx.AsyncClient(proxy=I2PD_HTTP_PROXY, timeout=60.0) as client:
        resp = await client.get(url, headers={"User-Agent": "Abyssal-Wayback/1.0"})
        snap_meta = wb_storage.store_snapshot(url=url, content=resp.text, status_code=resp.status_code)
        await wb_db.add_snapshot(
            url=url, snapshot_time=snap_meta["snapshot_time"],
            title="", status_code=resp.status_code,
            content_type=resp.headers.get("content-type", "text/html"),
            file_path=snap_meta["file_path"], size_bytes=snap_meta["size_bytes"],
        )
        return snap_meta


# ── Page viewer (public) ──────────────────────────────────────


@router.get("/pages/{page_id}")
async def get_page(page_id: int):
    page = await search_db.get_page(page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return page


@router.get("/pages/{page_id}/view")
async def view_page(page_id: int, raw: bool = Query(False)):
    page = await search_db.get_page(page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    if raw:
        return {"content": page["content"], "url": page["url"]}
    rewritten = rewrite_external_urls(page["content"], page["url"])
    return {"content": rewritten, "url": page["url"]}
