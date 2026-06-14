from typing import Optional

import aiosqlite

from abyssal.config import DB_PATH


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    return db


async def search_pages(
    q: str,
    language: str = "",
    site_type: str = "",
    page: int = 1,
    per_page: int = 20,
) -> dict:
    offset = (page - 1) * per_page
    db = await get_db()

    conditions = ["pages_fts MATCH ?"]
    params = [q]

    fts_cols = "title, content, description, keywords"

    if language:
        conditions.append("p.language = ?")
        params.append(language)
    if site_type:
        conditions.append("p.site_type = ?")
        params.append(site_type)

    where = " AND ".join(conditions)

    count_row = await db.execute_fetchall(
        f"SELECT COUNT(*) as total FROM pages_fts "
        f"JOIN crawled_pages p ON pages_fts.rowid = p.id "
        f"WHERE {where}",
        params,
    )
    total = count_row[0]["total"] if count_row else 0

    rows = await db.execute_fetchall(
        f"SELECT p.id, p.url, p.title, p.description, p.language, p.site_type, "
        f"p.b32, p.address_helper, p.crawled_at, p.status_code, "
        f"rank "
        f"FROM pages_fts "
        f"JOIN crawled_pages p ON pages_fts.rowid = p.id "
        f"WHERE {where} "
        f"ORDER BY rank "
        f"LIMIT ? OFFSET ?",
        params + [per_page, offset],
    )

    results = []
    for r in rows:
        result = dict(r)
        snippet = await _get_snippet(db, r["id"], q)
        result["snippet"] = snippet
        results.append(result)

    await db.close()

    return {
        "results": results,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": max(1, (total + per_page - 1) // per_page) if total > 0 else 0,
    }


async def _get_snippet(db: aiosqlite.Connection, page_id: int, query: str, context_chars: int = 150) -> str:
    try:
        rows = await db.execute_fetchall(
            f"SELECT snippet(pages_fts, 1, '<b>', '</b>', '...', {context_chars}) as sn "
            f"FROM pages_fts WHERE rowid = ? AND pages_fts MATCH ?",
            (page_id, query),
        )
        if rows and rows[0]["sn"]:
            return rows[0]["sn"]
    except Exception:
        pass

    rows = await db.execute_fetchall(
        "SELECT description FROM crawled_pages WHERE id = ?", (page_id,)
    )
    if rows and rows[0]["description"]:
        desc = rows[0]["description"]
        return desc[:context_chars * 2]

    return ""


async def get_page(page_id: int) -> Optional[dict]:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM crawled_pages WHERE id = ?", (page_id,)
    )
    await db.close()
    return dict(rows[0]) if rows else None


async def get_site(hostname: str) -> Optional[dict]:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM site_status WHERE hostname = ?", (hostname,)
    )
    if not rows:
        await db.close()
        return None
    site = dict(rows[0])

    pages = await db.execute_fetchall(
        "SELECT id, url, title, language, site_type, crawled_at "
        "FROM crawled_pages WHERE url LIKE ? "
        "ORDER BY crawled_at DESC LIMIT 50",
        (f"%{hostname}%",),
    )
    site["pages"] = [dict(p) for p in pages]
    await db.close()
    return site


async def get_sites(
    language: str = "",
    site_type: str = "",
    online: Optional[bool] = None,
    page: int = 1,
    per_page: int = 50,
) -> dict:
    offset = (page - 1) * per_page
    db = await get_db()

    conditions: list[str] = []
    params: list[str] = []

    if language:
        conditions.append("language = ?")
        params.append(language)
    if site_type:
        conditions.append("site_type = ?")
        params.append(site_type)
    if online is not None:
        if online:
            conditions.append("checks_online > checks_offline AND checks_online > 0")
        else:
            conditions.append("checks_offline >= checks_online OR checks_online = 0")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    base_query = (
        f"FROM site_status s "
        f"LEFT JOIN crawled_pages p ON s.hostname = SUBSTR(p.url, INSTR(p.url, '://') + 3) "
        f"AND p.id = (SELECT id FROM crawled_pages WHERE url LIKE '%' || s.hostname ORDER BY crawled_at DESC LIMIT 1) "
    )

    count_row = await db.execute_fetchall(
        f"SELECT COUNT(*) as total {base_query} {where}", params,
    )
    total = count_row[0]["total"] if count_row else 0

    rows = await db.execute_fetchall(
        f"SELECT s.*, COALESCE(p.title, '') as title, COALESCE(p.language, '') as language, "
        f"COALESCE(p.site_type, 'website') as site_type "
        f"{base_query} {where} "
        f"ORDER BY s.last_crawled DESC "
        f"LIMIT ? OFFSET ?",
        params + [per_page, offset],
    )

    await db.close()

    seen: dict[str, dict] = {}
    for r in rows:
        dr = dict(r)
        if dr["hostname"] not in seen:
            seen[dr["hostname"]] = dr

    return {
        "results": list(seen.values()),
        "total": total,
        "page": page,
        "per_page": per_page,
    }


async def get_facets() -> dict:
    db = await get_db()

    languages = await db.execute_fetchall(
        "SELECT language, COUNT(*) as count FROM site_status s "
        "JOIN crawled_pages p ON s.hostname = SUBSTR(p.url, INSTR(p.url, '://') + 3) "
        "WHERE language != '' "
        "GROUP BY language ORDER BY count DESC"
    )

    site_types = await db.execute_fetchall(
        "SELECT site_type, COUNT(*) as count FROM site_status s "
        "JOIN crawled_pages p ON s.hostname = SUBSTR(p.url, INSTR(p.url, '://') + 3) "
        "WHERE site_type != '' AND site_type != 'website' "
        "GROUP BY site_type ORDER BY count DESC"
    )

    await db.close()
    return {
        "languages": [dict(r) for r in languages],
        "site_types": [dict(r) for r in site_types],
    }
