from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from abyssal.config import ARCHIVE_ROOT

logger = logging.getLogger(__name__)


def _host_dir(url: str) -> Path:
    parsed = urlparse(url)
    host = parsed.netloc or parsed.hostname or "unknown"
    safe = "".join(c if c.isalnum() or c in ".-_" else "_" for c in host)
    return ARCHIVE_ROOT / safe


def _snapshot_filename(url: str, status_code: int, now: datetime) -> tuple[str, str]:
    ts = now.strftime("%Y%m%d_%H%M%S")
    h = hashlib.sha256(url.encode()).hexdigest()[:8]
    filename = f"{ts}_{status_code}_{h}.html"
    return ts, filename


def store_snapshot(url: str, content: str, status_code: int = 200,
                   content_type: str = "text/html",
                   captured_at: Optional[datetime] = None) -> dict:
    now = captured_at or datetime.now(timezone.utc)
    ts, filename = _snapshot_filename(url, status_code, now)
    host_dir = _host_dir(url)
    host_dir.mkdir(parents=True, exist_ok=True)

    file_path = host_dir / filename
    content_bytes = content.encode("utf-8")
    file_path.write_bytes(content_bytes)

    meta = {
        "snapshot_time": now.isoformat(),
        "file_path": str(file_path),
        "url": url,
        "status_code": status_code,
        "content_type": content_type,
        "size_bytes": len(content_bytes),
    }
    logger.info("Stored snapshot for %s → %s (%d bytes)", url, file_path, len(content_bytes))
    return meta


def load_snapshot(file_path: str) -> Optional[str]:
    p = Path(file_path)
    if p.exists() and p.is_file():
        return p.read_text(encoding="utf-8")
    logger.warning("Snapshot file not found: %s", file_path)
    return None


def delete_snapshot(file_path: str) -> bool:
    p = Path(file_path)
    if p.exists() and p.is_file():
        p.unlink()
        logger.info("Deleted snapshot file: %s", file_path)
        return True
    return False


def host_snapshots(url: str) -> list[dict]:
    host_dir = _host_dir(url)
    if not host_dir.exists():
        return []

    results = []
    for f in sorted(host_dir.iterdir()):
        if f.is_file() and f.suffix == ".html":
            parts = f.stem.split("_")
            ts_str = ""
            status_code = 0
            if len(parts) >= 3:
                ts_str = f"{parts[0]}_{parts[1]}"
                try:
                    status_code = int(parts[2])
                except ValueError:
                    status_code = 0
            try:
                dt = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
                dt = dt.replace(tzinfo=timezone.utc)
                snapshot_time = dt.isoformat()
            except ValueError:
                snapshot_time = ts_str

            results.append({
                "snapshot_time": snapshot_time,
                "file_path": str(f),
                "url": url,
                "status_code": status_code,
                "size_bytes": f.stat().st_size,
            })
    return results
