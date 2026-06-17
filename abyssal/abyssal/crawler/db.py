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
            UNIQUE(job_id, url),
            FOREIGN KEY (job_id) REFERENCES crawl_jobs(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS site_status (
            hostname TEXT PRIMARY KEY,
            b32 TEXT DEFAULT '',
            address_helper TEXT DEFAULT '',
            checks_online INTEGER DEFAULT 0,
            checks_offline INTEGER DEFAULT 0,
            checks_limited INTEGER DEFAULT 0,
            last_status INTEGER DEFAULT 0,
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
    # Migrate existing DBs that lack the new columns
    for col in ("checks_limited", "last_status", "created_at", "recrawl_at"):
        try:
            if col in ("checks_limited", "last_status"):
                await db.execute(f"ALTER TABLE site_status ADD COLUMN {col} INTEGER DEFAULT 0")
            elif col == "created_at":
                await db.execute("ALTER TABLE site_status ADD COLUMN created_at TEXT")
                await db.execute("UPDATE site_status SET created_at = COALESCE(last_crawled, datetime('now')) WHERE created_at IS NULL")
            else:
                await db.execute("ALTER TABLE site_status ADD COLUMN recrawl_at TEXT")
            await db.commit()
            logger.info("Added column %s to site_status", col)
        except Exception:
            pass
    for col in ("pages_failed", "pages_limited"):
        try:
            await db.execute(f"ALTER TABLE crawl_jobs ADD COLUMN {col} INTEGER DEFAULT 0")
            await db.commit()
            logger.info("Added column %s to crawl_jobs", col)
        except Exception:
            pass
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
        "INSERT OR IGNORE INTO crawl_queue (job_id, url, depth) VALUES (?, ?, 0)",
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


async def inc_job_failed(job_id: int):
    db = await get_db()
    await db.execute("UPDATE crawl_jobs SET pages_failed = pages_failed + 1 WHERE id = ?", (job_id,))
    await db.commit()
    await db.close()


async def inc_job_limited(job_id: int):
    db = await get_db()
    await db.execute("UPDATE crawl_jobs SET pages_limited = pages_limited + 1 WHERE id = ?", (job_id,))
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


async def save_failed_page(job_id: int, url: str, status_code: int, depth: int, error: str = ""):
    """Save a failed URL to crawled_pages (without FTS5 indexing) and increment the appropriate counter.

    - status_code == 429         → increments pages_limited
    - status_code >= 400 or 0    → increments pages_failed
    """
    db = await get_db()
    await db.execute(
        """INSERT INTO crawled_pages
           (job_id, url, title, content, status_code, depth, description)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (job_id, url, f"HTTP {status_code}", "", status_code, depth,
         error or f"HTTP {status_code}" if status_code else error),
    )
    if status_code == 429:
        await db.execute("UPDATE crawl_jobs SET pages_limited = pages_limited + 1 WHERE id = ?", (job_id,))
    else:
        await db.execute("UPDATE crawl_jobs SET pages_failed = pages_failed + 1 WHERE id = ?", (job_id,))
    await db.commit()
    await db.close()


async def enqueue_urls(job_id: int, urls: list[tuple[str, int]]):
    """Add URLs to the crawl queue, skipping any already crawled or already queued."""
    db = await get_db()
    for url, depth in urls:
        # Skip if already crawled
        already_crawled = await db.execute_fetchall(
            "SELECT 1 FROM crawled_pages WHERE job_id = ? AND url = ?", (job_id, url)
        )
        if already_crawled:
            continue
        # INSERT OR IGNORE handles the UNIQUE(job_id, url) constraint silently
        try:
            await db.execute(
                "INSERT OR IGNORE INTO crawl_queue (job_id, url, depth) VALUES (?, ?, ?)",
                (job_id, url, depth),
            )
        except Exception as e:
            logger.debug("Could not enqueue %s: %s", url, e)
    await db.commit()
    await db.close()


async def upsert_site_status(
    hostname: str,
    online: bool = False,
    limited: bool = False,
    b32: str = "",
    address_helper: str = "",
    status_code: int = 0,
):
    db = await get_db()
    existing = await db.execute_fetchall(
        "SELECT * FROM site_status WHERE hostname = ?", (hostname,)
    )
    now = datetime.now(timezone.utc).isoformat()
    if existing:
        if online:
            await db.execute(
                "UPDATE site_status SET checks_online = checks_online + 1, last_seen_online = ?, "
                "last_crawled = ?, last_status = ?, "
                "b32 = CASE WHEN ? != '' THEN ? ELSE b32 END, "
                "address_helper = CASE WHEN ? != '' THEN ? ELSE address_helper END "
                "WHERE hostname = ?",
                (now, now, status_code, b32, b32, address_helper, address_helper, hostname),
            )
        elif limited:
            await db.execute(
                "UPDATE site_status SET checks_limited = checks_limited + 1, "
                "last_crawled = ?, last_status = ?, "
                "b32 = CASE WHEN ? != '' THEN ? ELSE b32 END, "
                "address_helper = CASE WHEN ? != '' THEN ? ELSE address_helper END "
                "WHERE hostname = ?",
                (now, status_code, b32, b32, address_helper, address_helper, hostname),
            )
        else:
            await db.execute(
                "UPDATE site_status SET checks_offline = checks_offline + 1, last_seen_offline = ?, "
                "last_crawled = ?, last_status = ?, "
                "b32 = CASE WHEN ? != '' THEN ? ELSE b32 END, "
                "address_helper = CASE WHEN ? != '' THEN ? ELSE address_helper END "
                "WHERE hostname = ?",
                (now, now, status_code, b32, b32, address_helper, address_helper, hostname),
            )
    else:
        if online:
            await db.execute(
                "INSERT INTO site_status (hostname, b32, address_helper, checks_online, checks_offline, checks_limited, last_status, last_seen_online, last_crawled, created_at) "
                "VALUES (?, ?, ?, 1, 0, 0, ?, ?, ?, ?)",
                (hostname, b32, address_helper, status_code, now, now, now),
            )
        elif limited:
            await db.execute(
                "INSERT INTO site_status (hostname, b32, address_helper, checks_online, checks_offline, checks_limited, last_status, last_crawled, created_at) "
                "VALUES (?, ?, ?, 0, 0, 1, ?, ?, ?)",
                (hostname, b32, address_helper, status_code, now, now),
            )
        else:
            await db.execute(
                "INSERT INTO site_status (hostname, b32, address_helper, checks_online, checks_offline, checks_limited, last_status, last_seen_offline, last_crawled, created_at) "
                "VALUES (?, ?, ?, 0, 1, 0, ?, ?, ?, ?)",
                (hostname, b32, address_helper, status_code, now, now, now),
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


def recrawl_interval_for_status(status_code: int) -> int:
    """Return recrawl interval in hours based on the last HTTP status code."""
    if status_code == 0 or status_code >= 500:
        return 168  # connection error / server error → 7 days
    if status_code == 429:
        return 72   # rate limited → 3 days
    if 400 <= status_code < 500:
        return 72   # client error (403, 404, etc.) → 3 days
    return 24       # 200 OK or other success → 1 day


async def get_auto_crawl_sites() -> list[tuple[str, int]]:
    """Return (hostname, recrawl_interval_hours) for all sites due for recrawl.
    
    Checks recrawl_at first (if set); otherwise falls back to last_crawled + interval.
    """
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT hostname, last_status, last_crawled, recrawl_at FROM site_status"
    )
    await db.close()
    now = datetime.now(timezone.utc)
    due: list[tuple[str, int]] = []
    for r in rows:
        interval = recrawl_interval_for_status(r["last_status"])
        recrawl_at = r["recrawl_at"]
        last_crawled = r["last_crawled"]
        if recrawl_at:
            try:
                scheduled = datetime.fromisoformat(recrawl_at)
                if scheduled <= now:
                    due.append((r["hostname"], interval))
                continue
            except:
                pass
        if last_crawled is None:
            due.append((r["hostname"], interval))
        else:
            try:
                last = datetime.fromisoformat(last_crawled)
                if (now - last).total_seconds() > interval * 3600:
                    due.append((r["hostname"], interval))
            except:
                due.append((r["hostname"], interval))
    return due


async def get_scheduled_sites() -> list[dict]:
    """Return sites with a future recrawl_at timestamp (scheduled for recrawl)."""
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT hostname, b32, last_status, recrawl_at FROM site_status "
        "WHERE recrawl_at IS NOT NULL AND recrawl_at > datetime('now') "
        "ORDER BY recrawl_at ASC"
    )
    await db.close()
    return [dict(r) for r in rows]


async def set_recrawl_at(hostname: str, recrawl_at: str):
    """Set the recrawl_at timestamp for a hostname."""
    db = await get_db()
    await db.execute("UPDATE site_status SET recrawl_at = ? WHERE hostname = ?", (recrawl_at, hostname))
    await db.commit()
    await db.close()


async def clear_recrawl_at(hostname: str):
    """Clear the recrawl_at timestamp (crawl is starting now)."""
    db = await get_db()
    await db.execute("UPDATE site_status SET recrawl_at = NULL WHERE hostname = ?", (hostname,))
    await db.commit()
    await db.close()


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


async def get_active_job_for_hostname(hostname: str) -> Optional[int]:
    """
    Return the ID of a currently running/pending/paused job whose seed URL
    contains `hostname`, or None if no such job exists.

    Used by the scheduler to avoid spawning duplicate recrawl jobs.
    Unlike the old get_job_for_hostname this ONLY matches active statuses,
    so completed/failed runs never block a new scheduled recrawl.
    """
    db = await get_db()
    rows = await db.execute_fetchall(
        """SELECT id FROM crawl_jobs
           WHERE url LIKE ?
             AND status IN ('running', 'pending', 'paused')
           ORDER BY created_at DESC
           LIMIT 1""",
        (f"%{hostname}%",),
    )
    await db.close()
    return rows[0]["id"] if rows else None


async def get_addressbook(
    q: str = "",
    page: int = 1,
    per_page: int = 100,
) -> dict:
    """
    Return all known .i2p hostnames with their b32 addresses for the public
    addressbook page.  Supports optional text filter across hostname and b32.
    """
    db = await get_db()
    offset = (page - 1) * per_page

    if q:
        where  = "WHERE (hostname LIKE ? OR b32 LIKE ?)"
        params: list = [f"%{q}%", f"%{q}%"]
    else:
        where  = ""
        params = []

    total_rows = await db.execute_fetchall(
        f"SELECT COUNT(*) AS n FROM site_status {where}", params
    )
    total = total_rows[0]["n"] if total_rows else 0

    rows = await db.execute_fetchall(
        f"""SELECT
                hostname,
                b32,
                address_helper                                      AS base64,
                last_status,
                (checks_online > 0)                                 AS ever_online,
                (checks_online > 0 AND checks_online >= checks_offline AND checks_online >= checks_limited) AS likely_online,
                last_seen_online,
                last_crawled                                        AS last_seen,
                created_at                                          AS added_at,
                recrawl_at
            FROM site_status
            {where}
            ORDER BY hostname ASC
            LIMIT ? OFFSET ?""",
        (*params, per_page, offset),
    )
    await db.close()
    return {
        "sites":    [dict(r) for r in rows],
        "total":    total,
        "page":     page,
        "per_page": per_page,
    }
