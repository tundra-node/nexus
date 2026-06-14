import logging
from datetime import datetime, timezone
from typing import Optional

import aiosqlite

from abyssal.config import DB_PATH

logger = logging.getLogger(__name__)


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    return db


async def init_db():
    db = await get_db()
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS crawl_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            max_pages INTEGER DEFAULT 0,
            max_depth INTEGER DEFAULT 5,
            status TEXT DEFAULT 'pending',
            pages_crawled INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            finished_at TEXT,
            concurrency INTEGER DEFAULT 3,
            delay_seconds REAL DEFAULT 2.0,
            spawned_by INTEGER DEFAULT NULL
        );

        CREATE TABLE IF NOT EXISTS crawled_pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            url TEXT NOT NULL,
            title TEXT DEFAULT '',
            content TEXT DEFAULT '',
            status_code INTEGER,
            depth INTEGER DEFAULT 0,
            crawled_at TEXT DEFAULT (datetime('now')),
            language TEXT DEFAULT '',
            site_type TEXT DEFAULT '',
            description TEXT DEFAULT '',
            keywords TEXT DEFAULT '',
            b32 TEXT DEFAULT '',
            address_helper TEXT DEFAULT '',
            FOREIGN KEY (job_id) REFERENCES crawl_jobs(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS crawl_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            url TEXT NOT NULL,
            depth INTEGER DEFAULT 0,
            FOREIGN KEY (job_id) REFERENCES crawl_jobs(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS site_status (
            hostname TEXT PRIMARY KEY,
            b32 TEXT DEFAULT '',
            address_helper TEXT DEFAULT '',
            checks_online INTEGER DEFAULT 0,
            checks_offline INTEGER DEFAULT 0,
            last_seen_online TEXT,
            last_seen_offline TEXT,
            last_crawled TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS site_links (
            source_hostname TEXT NOT NULL,
            target_hostname TEXT NOT NULL,
            count INTEGER DEFAULT 1,
            first_seen TEXT DEFAULT (datetime('now')),
            last_seen TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (source_hostname, target_hostname)
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(
            title, content, description, keywords,
            content='crawled_pages', content_rowid='id',
            tokenize='porter unicode61'
        );
    """)
    await db.commit()
    await db.close()
    logger.info("Crawler database initialized with FTS5 search")


async def create_job(url: str, max_pages: int = 0, max_depth: int = 5,
                     concurrency: int = 3, delay_seconds: float = 2.0,
                     spawned_by: int = 0) -> int:
    db = await get_db()
    cur = await db.execute(
        "INSERT INTO crawl_jobs (url, max_pages, max_depth, concurrency, delay_seconds, spawned_by) VALUES (?, ?, ?, ?, ?, ?)",
        (url, max_pages, max_depth, concurrency, delay_seconds, spawned_by if spawned_by else None),
    )
    job_id = cur.lastrowid
    await db.execute(
        "INSERT INTO crawl_queue (job_id, url, depth) VALUES (?, ?, 0)",
        (job_id, url),
    )
    await db.commit()
    await db.close()
    return job_id


async def get_jobs() -> list[dict]:
    db = await get_db()
    rows = await db.execute_fetchall("SELECT * FROM crawl_jobs ORDER BY created_at DESC")
    await db.close()
    return [dict(r) for r in rows]


async def get_job(job_id: int) -> Optional[dict]:
    db = await get_db()
    rows = await db.execute_fetchall("SELECT * FROM crawl_jobs WHERE id = ?", (job_id,))
    await db.close()
    return dict(rows[0]) if rows else None


async def update_job(job_id: int, **kwargs):
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values())
    db = await get_db()
    await db.execute(f"UPDATE crawl_jobs SET {sets} WHERE id = ?", (*vals, job_id))
    await db.commit()
    await db.close()


async def inc_job_pages(job_id: int):
    db = await get_db()
    await db.execute("UPDATE crawl_jobs SET pages_crawled = pages_crawled + 1 WHERE id = ?", (job_id,))
    await db.commit()
    await db.close()


async def get_job_pages_crawled(job_id: int) -> int:
    db = await get_db()
    row = await db.execute_fetchall("SELECT pages_crawled FROM crawl_jobs WHERE id = ?", (job_id,))
    await db.close()
    return row[0]["pages_crawled"] if row else 0


async def get_next_queue_item(job_id: int) -> Optional[dict]:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM crawl_queue WHERE job_id = ? ORDER BY id ASC LIMIT 1",
        (job_id,),
    )
    if not rows:
        await db.close()
        return None
    item = dict(rows[0])
    await db.execute("DELETE FROM crawl_queue WHERE id = ?", (item["id"],))
    await db.commit()
    await db.close()
    return item


async def page_exists_in_job(job_id: int, url: str) -> bool:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT 1 FROM crawled_pages WHERE job_id = ? AND url = ?", (job_id, url)
    )
    await db.close()
    return len(rows) > 0


async def save_page(job_id: int, url: str, title: str, content: str,
                    status_code: int, depth: int,
                    language: str = "", site_type: str = "",
                    description: str = "", keywords: str = "",
                    b32: str = "", address_helper: str = ""):
    db = await get_db()
    cur = await db.execute(
        """INSERT INTO crawled_pages
           (job_id, url, title, content, status_code, depth, language, site_type, description, keywords, b32, address_helper)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (job_id, url, title, content, status_code, depth, language, site_type, description, keywords, b32, address_helper),
    )
    page_id = cur.lastrowid

    await db.execute(
        "INSERT INTO pages_fts (rowid, title, content, description, keywords) VALUES (?, ?, ?, ?, ?)",
        (page_id, title, content, description, keywords),
    )
    await db.commit()
    await db.close()
    return page_id


async def enqueue_urls(job_id: int, urls: list[tuple[str, int]]):
    db = await get_db()
    for url, depth in urls:
        exists = await page_exists_in_job(job_id, url)
        if not exists:
            try:
                await db.execute(
                    "INSERT INTO crawl_queue (job_id, url, depth) VALUES (?, ?, ?)",
                    (job_id, url, depth),
                )
            except Exception:
                pass
    await db.commit()
    await db.close()


async def upsert_site_status(hostname: str, online: bool, b32: str = "", address_helper: str = ""):
    db = await get_db()
    existing = await db.execute_fetchall(
        "SELECT * FROM site_status WHERE hostname = ?", (hostname,)
    )
    now = datetime.now(timezone.utc).isoformat()
    if existing:
        if online:
            await db.execute(
                "UPDATE site_status SET checks_online = checks_online + 1, last_seen_online = ?, "
                "last_crawled = ?, b32 = CASE WHEN ? != '' THEN ? ELSE b32 END, "
                "address_helper = CASE WHEN ? != '' THEN ? ELSE address_helper END "
                "WHERE hostname = ?",
                (now, now, b32, b32, address_helper, address_helper, hostname),
            )
        else:
            await db.execute(
                "UPDATE site_status SET checks_offline = checks_offline + 1, last_seen_offline = ?, "
                "last_crawled = ?, b32 = CASE WHEN ? != '' THEN ? ELSE b32 END, "
                "address_helper = CASE WHEN ? != '' THEN ? ELSE address_helper END "
                "WHERE hostname = ?",
                (now, now, b32, b32, address_helper, address_helper, hostname),
            )
    else:
        if online:
            await db.execute(
                "INSERT INTO site_status (hostname, b32, address_helper, checks_online, checks_offline, "
                "last_seen_online, last_crawled) VALUES (?, ?, ?, 1, 0, ?, ?)",
                (hostname, b32, address_helper, now, now),
            )
        else:
            await db.execute(
                "INSERT INTO site_status (hostname, b32, address_helper, checks_online, checks_offline, "
                "last_seen_offline, last_crawled) VALUES (?, ?, ?, 0, 1, ?, ?)",
                (hostname, b32, address_helper, now, now),
            )
    await db.commit()
    await db.close()


async def get_site_status() -> list[dict]:
    db = await get_db()
    rows = await db.execute_fetchall("SELECT * FROM site_status ORDER BY last_crawled DESC")
    await db.close()
    return [dict(r) for r in rows]


async def get_seen_hostnames() -> list[str]:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT DISTINCT hostname FROM site_status ORDER BY hostname"
    )
    await db.close()
    return [r["hostname"] for r in rows]


async def get_job_for_hostname(hostname: str) -> Optional[int]:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT id FROM crawl_jobs WHERE url LIKE ? AND status != 'failed' ORDER BY created_at DESC LIMIT 1",
        (f"%{hostname}%",),
    )
    await db.close()
    return rows[0]["id"] if rows else None


async def record_site_link(source_hostname: str, target_hostname: str):
    db = await get_db()
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        """INSERT INTO site_links (source_hostname, target_hostname, count, first_seen, last_seen)
           VALUES (?, ?, 1, ?, ?)
           ON CONFLICT(source_hostname, target_hostname) DO UPDATE SET
               count = count + 1,
               last_seen = ?""",
        (source_hostname, target_hostname, now, now, now),
    )
    await db.commit()
    await db.close()


async def get_auto_crawl_sites() -> list[str]:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT hostname FROM site_status "
        "WHERE last_crawled IS NULL OR last_crawled < datetime('now', '-24 hours')"
        "ORDER BY last_crawled ASC"
    )
    await db.close()
    return [r["hostname"] for r in rows]


async def get_graph_data() -> dict:
    db = await get_db()
    nodes_raw = await db.execute_fetchall("""
        SELECT
            s.hostname AS id,
            s.hostname AS label,
            s.b32,
            s.last_crawled,
            COALESCE(p.language, '') AS language,
            COALESCE(p.site_type, 'website') AS site_type,
            COALESCE(p.title, s.hostname) AS title,
            s.checks_online > s.checks_offline OR s.checks_online > 0 AS online
        FROM site_status s
        LEFT JOIN (
            SELECT hostname, language, site_type, title
            FROM (
                SELECT
                    SUBSTR(url, INSTR(url, '://') + 3) AS hostname,
                    language, site_type, title,
                    ROW_NUMBER() OVER (PARTITION BY SUBSTR(url, INSTR(url, '://') + 3) ORDER BY crawled_at DESC) AS rn
                FROM crawled_pages
                WHERE language != '' OR site_type != '' OR title != ''
            ) t WHERE rn = 1
        ) p ON p.hostname = s.hostname
        ORDER BY s.hostname
    """)
    nodes = [dict(r) for r in nodes_raw]
    links_raw = await db.execute_fetchall(
        "SELECT source_hostname, target_hostname, count FROM site_links ORDER BY count DESC"
    )
    links = [dict(r) for r in links_raw]
    await db.close()
    return {"nodes": nodes, "links": links}


async def delete_job(job_id: int):
    db = await get_db()
    page_ids = await db.execute_fetchall(
        "SELECT id FROM crawled_pages WHERE job_id = ?", (job_id,)
    )
    for pid in page_ids:
        await db.execute("DELETE FROM pages_fts WHERE rowid = ?", (pid["id"],))
    await db.execute("DELETE FROM crawl_jobs WHERE id = ?", (job_id,))
    await db.execute("DELETE FROM crawled_pages WHERE job_id = ?", (job_id,))
    await db.execute("DELETE FROM crawl_queue WHERE job_id = ?", (job_id,))
    await db.commit()
    await db.close()
