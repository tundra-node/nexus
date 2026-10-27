"""
Prism API — Addressbook Service
Manage i2pd addressbook subscriptions.
"""

import logging
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, APIRouter, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from common.config import API_KEY, I2PD_HTTP_PROXY, I2PD_CONF_PATH, I2PD_DATA_PATH

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ADDRESSBOOK_CSV = Path(I2PD_DATA_PATH) / "addressbook" / "addresses.csv"

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Prism Addressbook API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

router = APIRouter(prefix="/api/addressbook", tags=["addressbook"])


def _read_config() -> str:
    p = Path(I2PD_CONF_PATH)
    return p.read_text() if p.exists() else ""


def _write_config(text: str):
    Path(I2PD_CONF_PATH).write_text(text)


def _parse_subscriptions(config: str) -> list[str]:
    urls: list[str] = []
    in_section = False
    for line in config.splitlines():
        stripped = line.strip()
        if stripped.startswith("[addressbook]"):
            in_section = True
            continue
        if in_section and stripped.startswith("["):
            in_section = False
            continue
        if in_section and re.match(r'^subscriptions\s*=', stripped):
            val = stripped.split("=", 1)[1].strip()
            for u in val.split(","):
                u = u.strip().strip('"').strip("'")
                if u and not u.startswith("#"):
                    urls.append(u)
    return urls


def _parse_addresses_csv() -> list[dict]:
    entries: list[dict] = []
    p = Path(ADDRESSBOOK_CSV)
    if not p.exists():
        return entries
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(",", 1)
        if len(parts) == 2:
            hostname = parts[0].strip()
            b32 = parts[1].strip()
            if hostname.endswith(".i2p"):
                entries.append({"name": hostname, "b32": b32})
    return entries


def _save_addresses_csv(entries: list[dict]):
    lines = ["# i2pd addressbook - managed by Prism"]
    for e in sorted(entries, key=lambda x: x["name"]):
        lines.append(f"{e['name']},{e['b32']}")
    p = Path(ADDRESSBOOK_CSV)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines) + "\n")


@router.get("/subscriptions")
async def get_subscriptions(api_key: Optional[str] = Header(None, alias="x-api-key")):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    config = _read_config()
    urls = _parse_subscriptions(config)
    entries = _parse_addresses_csv()
    return {
        "subscriptions": [{"url": u, "name": u.rsplit("/", 1)[-1] or u} for u in urls],
        "total_entries": len(entries),
    }


class AddSubscriptionRequest(BaseModel):
    url: str


@router.post("/subscriptions")
async def add_subscription(
    body: AddSubscriptionRequest,
    api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")

    parsed = urlparse(body.url)
    if not parsed.netloc:
        raise HTTPException(status_code=400, detail="Invalid URL")

    try:
        async with httpx.AsyncClient(proxy=I2PD_HTTP_PROXY, timeout=60.0) as c:
            resp = await c.get(body.url)
            resp.raise_for_status()
            text = resp.text
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Timeout fetching addressbook")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch addressbook: {e}")

    new_entries: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(",", 1)
        if len(parts) != 2:
            parts = line.split("=", 1)
        if len(parts) == 2:
            hostname = parts[0].strip()
            b32 = parts[1].strip()
            if hostname.endswith(".i2p") and len(b32) > 10:
                new_entries.append({"name": hostname, "b32": b32})

    if not new_entries:
        raise HTTPException(status_code=400, detail="No valid entries found in addressbook")

    existing = _parse_addresses_csv()
    existing_map = {e["name"]: e for e in existing}
    for e in new_entries:
        existing_map[e["name"]] = e
    merged = list(existing_map.values())
    _save_addresses_csv(merged)

    config = _read_config()
    urls = _parse_subscriptions(config)
    if body.url not in urls:
        if any("subscriptions" in line for line in config.splitlines()):
            config = re.sub(
                r'(^subscriptions\s*=\s*.*?)(\s*#.*)?$',
                lambda m: m.group(1) + "," + body.url,
                config,
                flags=re.MULTILINE,
            )
        else:
            config += f"\n[addressbook]\nsubscriptions = {body.url}\n"
        _write_config(config)

    return {
        "status": "ok",
        "url": body.url,
        "entries_added": len(new_entries),
        "total_entries": len(merged),
    }


@router.delete("/subscriptions")
async def remove_subscription(
    url: str,
    api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")

    config = _read_config()
    new_config = re.sub(
        r'(^subscriptions\s*=\s*)(.*?)(\s*#.*)?$',
        lambda m: m.group(1) + re.sub(
            r',?\s*' + re.escape(url) + r'\s*,?', ',', m.group(2)
        ).strip(",").strip(),
        config,
        flags=re.MULTILINE,
    )
    if new_config != config:
        _write_config(new_config)

    return {"status": "ok", "url": url}


app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
