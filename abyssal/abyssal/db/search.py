from typing import Optional

import aiosqlite

from abyssal.config import DB_PATH


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
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
        f"rank, SUBSTR(p.url, INSTR(p.url, '://') + 3) AS hostname "
        f"FROM pages_fts "
        f"JOIN crawled_pages p ON pages_fts.rowid = p.id "
        f"WHERE {where} "
        f"ORDER BY rank "
        f"LIMIT ? OFFSET ?",
        params + [per_page * 3, offset],  # fetch extra for dedup
    )

    # Deduplicate by hostname, keep best-ranked page per site
    seen_hosts = {}
    for r in rows:
        host = r["hostname"].split("/")[0]  # strip path
        if host not in seen_hosts:
            seen_hosts[host] = r

    # Sort: hostname match first, then by rank
    query_lower = q.lower().replace(".i2p", "").replace("http://", "").replace("https://", "").strip()
    def sort_key(item):
        r = item[1]
        host = r["hostname"].split("/")[0].lower()
        # Boost if hostname contains query
        host_match = 0 if query_lower in host else 1
        # Boost if hostname starts with query
        starts_with = 0 if host.startswith(query_lower) else 1
        return (host_match, starts_with, r["rank"])

    sorted_hosts = sorted(seen_hosts.items(), key=sort_key)
    total_unique = len(seen_hosts)

    # Paginate after dedup
    page_results = sorted_hosts[(page-1)*per_page : page*per_page]

    results = []
    for host, r in page_results:
        result = dict(r)
        result["hostname"] = host
        snippet = await _get_snippet(db, r["id"], q)
        result["snippet"] = snippet
        results.append(result)

    await db.close()

    return {
        "results": results,
        "total": total_unique,
        "page": page,
        "per_page": per_page,
        "total_pages": max(1, (total_unique + per_page - 1) // per_page) if total_unique > 0 else 0,
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


def _build_page_tree(pages: list[dict]) -> list[dict]:
    """Group flat page list into a folder-tree structure by URL path segments."""
    tree: dict = {}
    for p in pages:
        url = p["url"]
        try:
            after_proto = url.split("://", 1)[1] if "://" in url else url
            path = "/" + after_proto.split("/", 1)[1] if "/" in after_proto else "/"
        except (IndexError, ValueError):
            path = "/"
        segments = [s for s in path.split("/") if s]
        node = tree
        for i, seg in enumerate(segments):
            is_last = i == len(segments) - 1
            if seg not in node:
                node[seg] = {"children": {}}
            if is_last:
                node[seg]["page"] = p
            node = node[seg]["children"]
    def _to_list(n: dict) -> list[dict]:
        items = []
        for name, val in n.items():
            has_page = "page" in val
            kids = _to_list(val.get("children", {}))
            if has_page and kids:
                items.append({"name": name, "type": "dir", "children": kids})
                items.append({"name": "(index)", "type": "file", "page": val["page"]})
            elif has_page:
                items.append({"name": name, "type": "file", "page": val["page"]})
            else:
                items.append({"name": name, "type": "dir", "children": kids})
        items.sort(key=lambda x: (1 if x["type"] == "file" else 0, x["name"].lower()))
        return items
    return _to_list(tree)


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
        "ORDER BY crawled_at ASC LIMIT 200",
        (f"%{hostname}%",),
    )
    site["pages"] = [dict(p) for p in pages]
    site["page_tree"] = _build_page_tree(site["pages"])
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
        conditions.append("latest.language = ?")
        params.append(language)
    if site_type:
        conditions.append("latest.site_type = ?")
        params.append(site_type)
    if online is not None:
        if online:
            conditions.append("s.checks_online > s.checks_offline AND s.checks_online > 0")
        else:
            conditions.append("s.checks_offline >= s.checks_online OR s.checks_online = 0")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    # Subquery gets latest page per hostname (avoids JOIN multiplication)
    base = (
        "FROM site_status s "
        "LEFT JOIN ("
        "  SELECT DISTINCT SUBSTR(url, INSTR(url, '://') + 3) AS hostname, "
        "    FIRST_VALUE(title) OVER (PARTITION BY SUBSTR(url, INSTR(url, '://') + 3) ORDER BY crawled_at DESC) AS title, "
        "    FIRST_VALUE(language) OVER (PARTITION BY SUBSTR(url, INSTR(url, '://') + 3) ORDER BY crawled_at DESC) AS language, "
        "    FIRST_VALUE(site_type) OVER (PARTITION BY SUBSTR(url, INSTR(url, '://') + 3) ORDER BY crawled_at DESC) AS site_type "
        "  FROM crawled_pages"
        ") latest ON s.hostname = latest.hostname "
    )

    count_row = await db.execute_fetchall(
        f"SELECT COUNT(*) as total {base} {where}", params,
    )
    total = count_row[0]["total"] if count_row else 0

    rows = await db.execute_fetchall(
        f"SELECT s.*, "
        f"COALESCE(latest.title, '') as title, "
        f"COALESCE(latest.language, '') as language, "
        f"COALESCE(latest.site_type, 'website') as site_type "
        f"{base} {where} "
        f"ORDER BY s.last_crawled DESC "
        f"LIMIT ? OFFSET ?",
        params + [per_page, offset],
    )

    await db.close()

    return {
        "results": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


async def get_facets() -> dict:
    db = await get_db()

    languages = await db.execute_fetchall(
        "SELECT ss.language, COUNT(*) as count FROM ("
        "  SELECT DISTINCT SUBSTR(url, INSTR(url, '://') + 3) AS hostname, language "
        "  FROM crawled_pages WHERE language != ''"
        ") ss "
        "GROUP BY ss.language ORDER BY count DESC"
    )

    site_types = await db.execute_fetchall(
        "SELECT ss.site_type, COUNT(*) as count FROM ("
        "  SELECT DISTINCT SUBSTR(url, INSTR(url, '://') + 3) AS hostname, site_type "
        "  FROM crawled_pages WHERE site_type != '' AND site_type != 'website'"
        ") ss "
        "GROUP BY ss.site_type ORDER BY count DESC"
    )

    await db.close()
    return {
        "languages": [dict(r) for r in languages],
        "site_types": [dict(r) for r in site_types],
    }
