"""Seed the crawler and wayback databases with sample data.

Abyssal normally fills its index by crawling the I2P network through a local
i2pd HTTP proxy. That makes UI work and demos awkward: you need a bootstrapped
router before you can see anything at all.

This script inserts a small, clearly-labelled sample corpus so the whole
interface (search, directory, site detail, link graph, wayback) can be explored
without a router.

    cd abyssal
    PYTHONPATH=. DB_PATH=../.local/data/crawler.db \
        ARCHIVE_ROOT=../.local/archive python scripts/seed_demo.py

Pass ``--force`` to seed when the database already has pages.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timedelta, timezone

from abyssal.config import ARCHIVE_ROOT
from abyssal.crawler.db import get_db as get_crawler_db
from abyssal.crawler.db import init_db
from abyssal.wayback.db import add_snapshot
from abyssal.wayback.db import get_db as get_wayback_db
from abyssal.wayback.db import init_wayback_db
from abyssal.wayback.storage import store_snapshot

logger = logging.getLogger("seed_demo")

# Every host below is a real I2P hostname, but the page text is written for
# this script. Do not treat it as captured content.
SITES: list[dict] = [
    {
        "hostname": "notbob.i2p",
        "title": "NotBob's I2P Links",
        "description": "A long-running hand-maintained directory of eepsites.",
        "keywords": "i2p, directory, links, eepsites",
        "site_type": "directory",
        "b32": "2uovh5w6qsmvzbnjhq4n3ezkzjrcx6lnc3lf3kvwjltbnrgxt6ga.b32.i2p",
        "pages": [
            (
                "/",
                "NotBob's I2P Links",
                "Hand curated links into the I2P network. Start with the search "
                "engines if you are new. Sites are checked roughly once a week and "
                "dead entries are moved to the archive section instead of deleted.",
            ),
            (
                "/search",
                "Search engines on I2P",
                "A short list of search engines that index eepsites. Each engine "
                "crawls on its own schedule, so coverage and freshness differ a lot "
                "between them. Abyssal is the newest of the set and the only one "
                "that keeps a public Wayback style archive.",
            ),
            (
                "/archive",
                "Dead eepsites",
                "Sites that stopped responding for more than three months. Kept "
                "here because people still link to them and because some have come "
                "back after a year offline. If a site here returns, it goes back to "
                "the main list at the next check.",
            ),
        ],
    },
    {
        "hostname": "stats.i2p",
        "title": "I2P Network Statistics",
        "description": "Live NetDB and router statistics for the I2P network.",
        "keywords": "i2p, netdb, statistics, routers, tunnels",
        "site_type": "stats",
        "b32": "8x5vqn4qmwf2tbnbcrztmvchgdcvfnfyx7nhgvkxnzpqhql2vkqq.b32.i2p",
        "pages": [
            (
                "/",
                "I2P Network Statistics",
                "Current router count, floodfill count, and tunnel build success "
                "rates. Numbers update every few minutes from a single monitoring "
                "router, so treat them as a sample rather than a census.",
            ),
            (
                "/netdb",
                "NetDB overview",
                "RouterInfo records known to this monitoring node, grouped by "
                "country and by transport. NTCP2 still carries the bulk of traffic "
                "while SSU2 handles the rest. LeaseSet churn is worth watching if "
                "you are debugging tunnel failures.",
            ),
            (
                "/tunnels",
                "Tunnel build statistics",
                "Exploratory and client tunnel build success rates over the last "
                "24 hours. A build rate below sixty percent usually means the "
                "router's clock is off or its firewall is dropping UDP.",
            ),
        ],
    },
    {
        "hostname": "zzz.i2p",
        "title": "ZZZ's I2P Notes",
        "description": "Protocol notes, proposals, and implementation details.",
        "keywords": "i2p, protocol, ntcp2, ssu2, proposals, specs",
        "site_type": "docs",
        "b32": "3w6btu7bhbwpugd2jnm5xvzkyfhkqhdxyxwz3lhzfnnbj2rl4baq.b32.i2p",
        "pages": [
            (
                "/",
                "ZZZ's I2P Notes",
                "Notes on the I2P wire protocol, written while implementing it. "
                "Most of this started as debugging output and turned into reference "
                "material that other implementers now read.",
            ),
            (
                "/ntcp2",
                "NTCP2 transport notes",
                "Handshake framing, Noise protocol choices, and the padding rules "
                "that make length analysis harder. Includes the reasoning behind "
                "the two byte length field and the replay window size.",
            ),
            (
                "/tunnel-build",
                "Tunnel build message format",
                "Structure of the tunnel build request and reply records, plus the "
                "shared random material that ties a batch together. Useful when "
                "reading logs from a router that keeps failing builds.",
            ),
        ],
    },
    {
        "hostname": "forum.i2p",
        "title": "I2P Forum",
        "description": "Discussion board for I2P users and developers.",
        "keywords": "i2p, forum, discussion, community",
        "site_type": "forum",
        "b32": "7pznwv4l5xrqhbkmyc6d2nsvf3tuqzeljx7bgmwnhk4rvt2ycqba.b32.i2p",
        "pages": [
            (
                "/",
                "I2P Forum",
                "Boards for router operation, eepsite hosting, and development. "
                "Registration is open but posting requires solving a small proof of "
                "work to keep spam down.",
            ),
            (
                "/viewforum?f=3",
                "Eepsite hosting",
                "Threads about running a server inside I2P: tunnel configuration, "
                "server tunnels, TLS inside the network, and why your site is not "
                "resolving for other people.",
            ),
            (
                "/viewtopic?t=812",
                "Search engine crawl behaviour",
                "Discussion of how often crawlers should revisit a site, how to "
                "read your access logs to spot them, and whether a site should "
                "advertise a crawl delay.",
            ),
        ],
    },
    {
        "hostname": "postman.i2p",
        "title": "Postman's I2P Tracker",
        "description": "Tracker for I2P email and torrents.",
        "keywords": "i2p, email, tracker, torrents, postman",
        "site_type": "service",
        "b32": "4fz3kjwqvyb2nrlxudc5mht7pgs6eaqzknvx2wbtfjrplmcqy3aa.b32.i2p",
        "pages": [
            (
                "/",
                "Postman's Tracker",
                "Announce URLs and account information for the long running I2P "
                "torrent tracker. Accounts are created on first announce, so there "
                "is nothing to sign up for.",
            ),
            (
                "/mail",
                "Mail relay notes",
                "How the mail relay handles unauthenticated senders and what the "
                "retry schedule looks like when a destination eepsite is offline.",
            ),
        ],
    },
    {
        "hostname": "identiguy.i2p",
        "title": "Identiguy Address Book",
        "description": "Large public address book of I2P hostnames.",
        "keywords": "i2p, addressbook, hostnames, subscriptions",
        "site_type": "directory",
        "b32": "6h2yxqwvbn3lrtkmucd4pja7sgz5efxqnvbt2wmcrkjplmqy3a.b32.i2p",
        "pages": [
            (
                "/",
                "Identiguy Address Book",
                "Hosts.txt subscriptions for I2P routers. Add the subscription URL "
                "in your router's address book settings and new hostnames arrive "
                "automatically.",
            ),
            (
                "/hosts.txt",
                "hosts.txt",
                "notbob.i2p=2uovh5w6qsmvzbnjhq4n3ezkzjrcx6lnc3lf3kvwjltbnrgxt6ga\n"
                "stats.i2p=8x5vqn4qmwf2tbnbcrztmvchgdcvfnfyx7nhgvkxnzpqhql2vkqq\n"
                "zzz.i2p=3w6btu7bhbwpugd2jnm5xvzkyfhkqhdxyxwz3lhzfnnbj2rl4baq",
            ),
        ],
    },
    {
        "hostname": "i2pd.i2p",
        "title": "i2pd Documentation",
        "description": "Documentation for the i2pd C++ router implementation.",
        "keywords": "i2p, i2pd, router, configuration, docker",
        "site_type": "docs",
        "b32": "5mzq4vbnw7hk2lrtucd3pja6sgz5efxqnvbt2wmcrkjplmqy3a.b32.i2p",
        "pages": [
            (
                "/",
                "i2pd Documentation",
                "Configuration reference for i2pd: transports, tunnel defaults, "
                "the HTTP proxy, the SAM bridge, and I2PControl.",
            ),
            (
                "/configuration",
                "Configuration options",
                "Most options have working defaults, so a fresh install only needs a "
                "datadir. The two that trip people up are the HTTP proxy port and "
                "whether I2PControl is enabled for external dashboards.",
            ),
            (
                "/docker",
                "Running i2pd in Docker",
                "Bridge networking works for outbound traffic but publishing a "
                "LeaseSet wants host networking, which is why the compose setup in "
                "many I2P stacks is Linux only.",
            ),
        ],
    },
    {
        "hostname": "plan.rc.i2p",
        "title": "I2P Roadmap",
        "description": "Planned protocol work and open research questions.",
        "keywords": "i2p, roadmap, research, proposals",
        "site_type": "docs",
        "b32": "2lq7xwvbn3hrktmucd4pja6sgz5efxqnvbt2wmcrkjplmqy3a.b32.i2p",
        "pages": [
            (
                "/",
                "I2P Roadmap",
                "Open work items grouped by area: transport, tunnel building, "
                "naming, and application protocols.",
            ),
            (
                "/naming",
                "Naming system work",
                "Address books are deliberately local. This page collects the "
                "proposals for making naming more usable without introducing a "
                "central authority.",
            ),
        ],
    },
]

# Source hostname -> target hostname -> link count
LINKS: dict[str, dict[str, int]] = {
    "notbob.i2p": {"stats.i2p": 4, "zzz.i2p": 3, "forum.i2p": 2, "identiguy.i2p": 6},
    "stats.i2p": {"notbob.i2p": 1, "zzz.i2p": 2},
    "zzz.i2p": {"forum.i2p": 3, "plan.rc.i2p": 2},
    "forum.i2p": {"i2pd.i2p": 3, "notbob.i2p": 1, "plan.rc.i2p": 1},
    "postman.i2p": {"forum.i2p": 2, "notbob.i2p": 1},
    "identiguy.i2p": {"notbob.i2p": 2, "stats.i2p": 1, "i2pd.i2p": 1},
    "i2pd.i2p": {"zzz.i2p": 2, "forum.i2p": 1},
    "plan.rc.i2p": {"zzz.i2p": 1, "forum.i2p": 1},
}


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _snapshot_html(hostname: str, title: str, body: str) -> str:
    return (
        "<!DOCTYPE html>\n<html><head><meta charset=\"utf-8\">"
        f"<title>{title}</title></head><body>"
        f"<h1>{title}</h1><p>{body}</p>"
        f"<p><small>sample snapshot of {hostname}</small></p>"
        "</body></html>"
    )


async def seed(force: bool = False) -> int:
    crawler = await get_crawler_db()
    existing = await crawler.execute_fetchall("SELECT COUNT(*) AS n FROM crawled_pages")
    count = existing[0]["n"] if existing else 0
    if count and not force:
        logger.error("Database already has %d pages. Re-run with --force to add demo rows anyway.", count)
        await crawler.close()
        return 1

    now = datetime.now(timezone.utc)

    cur = await crawler.execute(
        "INSERT INTO crawl_jobs (url, max_pages, max_depth, status, pages_crawled, "
        "created_at, finished_at, concurrency, delay_seconds) "
        "VALUES (?, ?, ?, 'finished', ?, ?, ?, ?, ?)",
        (
            "http://notbob.i2p/",
            0,
            5,
            sum(len(s["pages"]) for s in SITES),
            _iso(now - timedelta(hours=6)),
            _iso(now - timedelta(hours=5)),
            3,
            2.0,
        ),
    )
    job_id = cur.lastrowid
    await crawler.commit()

    page_ids: list[tuple[str, str, int]] = []

    for site in SITES:
        host = site["hostname"]
        for index, (path, title, body) in enumerate(site["pages"]):
            url = f"http://{host}{path}"
            crawled_at = _iso(now - timedelta(hours=5, minutes=index))
            cur = await crawler.execute(
                "INSERT INTO crawled_pages (job_id, url, title, content, status_code, "
                "depth, crawled_at, language, site_type, description, keywords, b32, "
                "address_helper) VALUES (?, ?, ?, ?, 200, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    job_id,
                    url,
                    title,
                    body,
                    index,
                    crawled_at,
                    "en",
                    site["site_type"],
                    site["description"],
                    site["keywords"],
                    site["b32"],
                    "identiguy.i2p",
                ),
            )
            page_ids.append((host, title, cur.lastrowid))

        await crawler.execute(
            "INSERT INTO site_status (hostname, b32, address_helper, checks_online, "
            "checks_offline, checks_limited, last_status, last_seen_online, "
            "last_crawled, created_at) VALUES (?, ?, ?, ?, 0, 1, 200, ?, ?, ?) "
            "ON CONFLICT(hostname) DO UPDATE SET b32 = excluded.b32, "
            "checks_online = excluded.checks_online, last_status = excluded.last_status, "
            "last_seen_online = excluded.last_seen_online, last_crawled = excluded.last_crawled",
            (
                host,
                site["b32"],
                "identiguy.i2p",
                6 + len(site["pages"]),
                _iso(now - timedelta(hours=5)),
                _iso(now - timedelta(hours=5)),
                _iso(now - timedelta(days=20)),
            ),
        )

    for source, targets in LINKS.items():
        for target, link_count in targets.items():
            await crawler.execute(
                "INSERT INTO site_links (source_hostname, target_hostname, count, "
                "first_seen, last_seen) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(source_hostname, target_hostname) DO UPDATE SET "
                "count = excluded.count, last_seen = excluded.last_seen",
                (
                    source,
                    target,
                    link_count,
                    _iso(now - timedelta(days=20)),
                    _iso(now - timedelta(hours=5)),
                ),
            )

    # Rebuild the external-content FTS index from crawled_pages.
    await crawler.execute("INSERT INTO pages_fts (pages_fts) VALUES ('rebuild')")
    await crawler.commit()
    await crawler.close()

    logger.info("Seeded %d pages across %d sites", len(page_ids), len(SITES))
    if not ARCHIVE_ROOT.exists():
        ARCHIVE_ROOT.mkdir(parents=True, exist_ok=True)

    wayback_count = 0
    for site in SITES:
        host = site["hostname"]
        path, title, body = site["pages"][0]
        for days_ago in (30, 14, 3):
            captured = now - timedelta(days=days_ago)
            snapshot_url = f"http://{host}{path}"
            payload = _snapshot_html(host, title, body)
            stored = store_snapshot(snapshot_url, payload, captured)
            await add_snapshot(
                url=snapshot_url,
                snapshot_time=_iso(captured),
                title=title,
                status_code=200,
                content_type="text/html",
                file_path=stored["file_path"],
                size_bytes=stored["size_bytes"],
                job_id=job_id,
            )
            wayback_count += 1

    wayback = await get_wayback_db()
    await wayback.close()

    logger.info("Seeded %d wayback snapshots", wayback_count)
    return 0


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="seed even if pages exist")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    await init_db()
    await init_wayback_db()
    return await seed(force=args.force)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
