"""
Prism API — I2P Browser Service
Proxy fetching + bookmarks.
"""

import json
import logging
import urllib.parse
from pathlib import Path
from typing import Optional, Dict, List

import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, FastAPI, HTTPException, Header, Query
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

from common.config import API_KEY, I2PD_HTTP_PROXY

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOOKMARKS_FILE = Path("/data/browser_bookmarks.json")

DEFAULT_BOOKMARKS = [
    {"name": "I2P Forum", "url": "http://i2pforum.i2p"},
]

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Prism Browser API", version="1.0.0")

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

router = APIRouter(prefix="/api/browser", tags=["browser"])


def _get_bookmarks() -> List[Dict[str, str]]:
    if BOOKMARKS_FILE.exists():
        try:
            return json.loads(BOOKMARKS_FILE.read_text())
        except Exception:
            pass
    return list(DEFAULT_BOOKMARKS)


def _save_bookmarks(bookmarks: List[Dict[str, str]]) -> None:
    BOOKMARKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    BOOKMARKS_FILE.write_text(json.dumps(bookmarks, indent=2))


def _rewrite_html(html: str, base_url: str) -> str:
    """Rewrite all links in HTML to go through the proxy."""
    soup = BeautifulSoup(html, "html.parser")
    proxy_base = f"/api/browser/proxy?api_key={API_KEY}&url="

    def rewrite_url(url: str) -> str:
        if not url or url.startswith("#") or url.startswith("javascript:"):
            return url
        absolute = urllib.parse.urljoin(base_url, url)
        return proxy_base + urllib.parse.quote(absolute, safe="")

    for tag, attr in [
        ("a", "href"), ("img", "src"), ("link", "href"),
        ("script", "src"), ("iframe", "src"), ("source", "src"),
        ("video", "src"), ("audio", "src"), ("form", "action"),
        ("area", "href"),
    ]:
        for el in soup.find_all(tag, **{attr: True}):
            el[attr] = rewrite_url(el[attr])

    return str(soup)


@router.get("/proxy")
async def proxy_get(
    url: str,
    api_key: Optional[str] = Header(None, alias="x-api-key"),
    api_key_query: Optional[str] = Query(None, alias="api_key"),
):
    """Fetch a .i2p URL via i2pd's HTTP proxy, rewriting links."""
    key = api_key or api_key_query
    if key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")

    parsed = urllib.parse.urlparse(url)
    if not parsed.netloc:
        raise HTTPException(status_code=400, detail="Invalid URL")

    try:
        async with httpx.AsyncClient(
            proxy=I2PD_HTTP_PROXY, timeout=120.0, follow_redirects=True
        ) as client:
            resp = await client.get(
                url,
                headers={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
            )
            content_type = resp.headers.get("content-type", "")

            if "text/html" in content_type or "application/xhtml" in content_type:
                html = _rewrite_html(resp.text, url)
                return HTMLResponse(content=html, status_code=resp.status_code)
            else:
                return Response(
                    content=resp.content,
                    status_code=resp.status_code,
                    media_type=content_type or "application/octet-stream",
                    headers={
                        h: v for h, v in resp.headers.items()
                        if h.lower() not in ("content-encoding", "transfer-encoding", "content-length")
                    },
                )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail=f"Timeout fetching {url}")
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail=f"Cannot connect to {url}")
    except Exception as e:
        logger.error("Proxy error for %s: %s", url, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bookmarks")
async def list_bookmarks(api_key: Optional[str] = Header(None, alias="x-api-key")):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return {"bookmarks": _get_bookmarks()}


class BookmarkEntry(BaseModel):
    name: str
    url: str


@router.post("/bookmarks")
async def save_bookmarks(
    body: list[BookmarkEntry],
    api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    _save_bookmarks([b.model_dump() for b in body])
    return {"status": "ok"}


app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
