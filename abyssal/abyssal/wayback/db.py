import logging
from typing import Optional

import aiosqlite

from abyssal.config import DB_PATH

logger = logging.getLogger(__name__)


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    return db


async def init_wayback_db():
    db = await get_db()
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS wayback_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            snapshot_time TEXT NOT NULL,
            title TEXT DEFAULT '',
            status_code INTEGER DEFAULT 200,
            content_type TEXT DEFAULT 'text/html',
            file_path TEXT NOT NULL,
            size_bytes INTEGER DEFAULT 0,
            job_id INTEGER DEFAULT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_wayback_url ON wayback_snapshots(url);
        CREATE INDEX IF NOT EXISTS idx_wayback_time ON wayback_snapshots(snapshot_time);
        CREATE INDEX IF NOT EXISTS idx_wayback_url_time ON wayback_snapshots(url, snapshot_time);

        CREATE TABLE IF NOT EXISTS wayback_urls (
            url TEXT PRIMARY KEY,
            first_captured TEXT DEFAULT (datetime('now')),
            last_captured TEXT DEFAULT (datetime('now')),
            capture_count INTEGER DEFAULT 1,
            schedule_interval INTEGER DEFAULT NULL,
            schedule_enabled INTEGER DEFAULT 0,
            title TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS wayback_schedule_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            action TEXT NOT NULL,
            details TEXT DEFAULT '',
            logged_at TEXT DEFAULT (datetime('now'))
        );
    """)
    await db.commit()
    await db.close()
    logger.info("Wayback database tables initialized")


async def add_snapshot(url: str, snapshot_time: str, title: str,
                       status_code: int, content_type: str,
                       file_path: str, size_bytes: int,
                       job_id: Optional[int] = None) -> int:
    db = await get_db()
    cur = await db.execute(
        """INSERT INTO wayback_snapshots
           (url, snapshot_time, title, status_code, content_type, file_path, size_bytes, job_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (url, snapshot_time, title, status_code, content_type, file_path, size_bytes, job_id),
    )
    snap_id = cur.lastrowid

    await db.execute(
        """INSERT INTO wayback_urls (url, last_captured, capture_count)
           VALUES (?, ?, 1)
           ON CONFLICT(url) DO UPDATE SET
               last_captured = excluded.last_captured,
               capture_count = capture_count + 1""",
        (url, snapshot_time),
    )
    await db.commit()
    await db.close()
    return snap_id


async def get_snapshots_for_url(url: str, limit: int = 500, offset: int = 0) -> list[dict]:
    db = await get_db()
    rows = await db.execute_fetchall(
        """SELECT id, url, snapshot_time, title, status_code, content_type, file_path, size_bytes, job_id
           FROM wayback_snapshots
           WHERE url = ?
           ORDER BY snapshot_time DESC
           LIMIT ? OFFSET ?""",
        (url, limit, offset),
    )
    await db.close()
    return [dict(r) for r in rows]


async def get_snapshot(snapshot_id: int) -> Optional[dict]:
    db = await get_db()
    rows = await db.execute_fetchall("SELECT * FROM wayback_snapshots WHERE id = ?", (snapshot_id,))
    await db.close()
    return dict(rows[0]) if rows else None


async def count_snapshots_for_url(url: str) -> int:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT COUNT(*) as cnt FROM wayback_snapshots WHERE url = ?", (url,),
    )
    await db.close()
    return rows[0]["cnt"] if rows else 0


async def get_all_tracked_urls(limit: int = 100, offset: int = 0) -> list[dict]:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM wayback_urls ORDER BY last_captured DESC LIMIT ? OFFSET ?",
        (limit, offset),
    )
    await db.close()
    return [dict(r) for r in rows]


async def count_tracked_urls() -> int:
    db = await get_db()
    rows = await db.execute_fetchall("SELECT COUNT(*) as cnt FROM wayback_urls")
    await db.close()
    return rows[0]["cnt"] if rows else 0


async def get_tracked_url(url: str) -> Optional[dict]:
    db = await get_db()
    rows = await db.execute_fetchall("SELECT * FROM wayback_urls WHERE url = ?", (url,))
    await db.close()
    return dict(rows[0]) if rows else None


async def upsert_tracked_url(url: str, title: str = "",
                              schedule_interval: Optional[int] = None) -> None:
    db = await get_db()
    if schedule_interval:
        await db.execute(
            """INSERT INTO wayback_urls (url, title, schedule_interval, schedule_enabled, last_captured)
               VALUES (?, ?, ?, 1, datetime('now'))
               ON CONFLICT(url) DO UPDATE SET
                   title = COALESCE(NULLIF(?, ''), title),
                   schedule_interval = ?,
                   schedule_enabled = 1""",
            (url, title, schedule_interval, title, schedule_interval),
        )
    else:
        # Use a real UPSERT so we handle the case where the row doesn't exist yet
        await db.execute(
            """INSERT INTO wayback_urls (url, title, last_captured, capture_count)
               VALUES (?, ?, datetime('now'), 0)
               ON CONFLICT(url) DO UPDATE SET
                   title = COALESCE(NULLIF(?, ''), title)""",
            (url, title, title),
        )
    await db.commit()
    await db.close()


async def get_scheduled_urls() -> list[dict]:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM wayback_urls WHERE schedule_enabled = 1 AND schedule_interval IS NOT NULL"
    )
    await db.close()
    return [dict(r) for r in rows]


async def update_schedule(url: str, interval_minutes: Optional[int],
                           enabled: bool = True) -> None:
    db = await get_db()
    await db.execute(
        "UPDATE wayback_urls SET schedule_interval = ?, schedule_enabled = ? WHERE url = ?",
        (interval_minutes, 1 if enabled else 0, url),
    )
    await db.commit()
    await db.close()


async def search_snapshots(q: str, limit: int = 50, offset: int = 0) -> list[dict]:
    db = await get_db()
    rows = await db.execute_fetchall(
        """SELECT id, url, snapshot_time, title, status_code, size_bytes
           FROM wayback_snapshots
           WHERE url LIKE ? OR title LIKE ?
           ORDER BY snapshot_time DESC
           LIMIT ? OFFSET ?""",
        (f"%{q}%", f"%{q}%", limit, offset),
    )
    await db.close()
    return [dict(r) for r in rows]


async def get_stats() -> dict:
    db = await get_db()
    total_snapshots = await db.execute_fetchall("SELECT COUNT(*) as cnt FROM wayback_snapshots")
    total_urls = await db.execute_fetchall("SELECT COUNT(*) as cnt FROM wayback_urls")
    total_size = await db.execute_fetchall("SELECT COALESCE(SUM(size_bytes), 0) as total FROM wayback_snapshots")
    recent = await db.execute_fetchall(
        """SELECT url, snapshot_time, title, status_code
           FROM wayback_snapshots
           ORDER BY snapshot_time DESC LIMIT 10"""
    )
    by_date = await db.execute_fetchall(
        """SELECT DATE(snapshot_time) as day, COUNT(*) as count
           FROM wayback_snapshots
           GROUP BY DATE(snapshot_time)
           ORDER BY day DESC LIMIT 30"""
    )
    await db.close()
    return {
        "total_snapshots": total_snapshots[0]["cnt"] if total_snapshots else 0,
        "total_urls": total_urls[0]["cnt"] if total_urls else 0,
        "total_size_bytes": total_size[0]["total"] if total_size else 0,
        "recent_snapshots": [dict(r) for r in recent],
        "snapshots_by_date": [dict(r) for r in by_date],
    }


async def log_schedule_action(url: str, action: str, details: str = "") -> None:
    db = await get_db()
    await db.execute(
        "INSERT INTO wayback_schedule_log (url, action, details) VALUES (?, ?, ?)",
        (url, action, details),
    )
    await db.commit()
    await db.close()


async def get_schedule_log(limit: int = 100) -> list[dict]:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM wayback_schedule_log ORDER BY logged_at DESC LIMIT ?", (limit,),
    )
    await db.close()
    return [dict(r) for r in rows]
