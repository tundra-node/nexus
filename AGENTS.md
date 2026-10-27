# Nexus — Agent Guide

## Overview

Nexus is a monorepo containing two connected I2P tools behind a shared nginx reverse proxy and i2pd instance:

| Directory | Name | Purpose | Auth |
|-----------|------|---------|------|
| `abyssal/` | **Abyssal** | Public I2P search engine + Wayback Machine + crawler | Search/Wayback read: public; Crawl admin: `api-key` |
| `prism/` | **Prism** | Private i2pd dashboard, I2P browser, addressbook | All routes: `x-api-key` |

## Quick Start

```sh
cd abyssal && docker compose up --build
```

- `http://localhost` — Abyssal search engine
- `http://localhost/dashboard/` — Prism dashboard

Dev key (both projects): `dev-key-12345`

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Vanilla HTML/CSS/JS (minimal, no framework — fast for I2P) |
| Backend | Python 3.11 FastAPI + httpx + aiosqlite + BeautifulSoup |
| Infrastructure | Docker Compose, nginx, purplei2p/i2pd |

## API Architecture (nginx routes)

| Route | Backend | Service |
|-------|---------|---------|
| `/` | Abyssal frontend | Search engine SPA |
| `/api/abyssal/*` | Abyssal backend | Search, crawl, Wayback, directory, graph |
| `/dashboard/*` | Prism frontend | Dashboard SPA |
| `/api/` (bare) | Prism router | Router health, status, bandwidth |
| `/api/router/*` | Prism router | Router dashboard endpoints |
| `/api/browser/*` | Prism browser | I2P proxy + link rewriting |
| `/api/addressbook/*` | Prism addressbook | Subscription management |

---

## Abyssal — Search Engine + Crawler + Wayback

### Endpoints

| Method | Route | Auth | Purpose |
|--------|-------|------|---------|
| GET | `/api/abyssal/search` | Public | FTS5 full-text search with BM25 ranking, snippets, language/site_type filters |
| GET | `/api/abyssal/facets` | Public | Available languages and site types |
| GET | `/api/abyssal/sites` | Public | Directory of discovered sites |
| GET | `/api/abyssal/sites/{hostname}` | Public | Site detail with pages |
| GET | `/api/abyssal/graph` | Public | Site link graph (nodes + edges) |
| GET | `/api/abyssal/site-status` | Public | Online/offline status of all known hosts |
| GET | `/api/abyssal/pages/{id}` | Public | Page detail |
| GET | `/api/abyssal/pages/{id}/view` | Public | Rendered HTML (URLs rewritten) |
| GET | `/api/abyssal/wayback/stats` | Public | Wayback archive statistics |
| GET | `/api/abyssal/wayback/urls` | Public | All tracked URLs |
| GET | `/api/abyssal/wayback/snapshots` | Public | Snapshots for a URL |
| GET | `/api/abyssal/wayback/snapshots/{id}/view` | Public | Rendered snapshot |
| POST | `/api/abyssal/crawl/start` | `api-key` | Start a crawl job |
| GET | `/api/abyssal/crawl/jobs` | `api-key` | List crawl jobs |
| DELETE | `/api/abyssal/crawl/jobs/{id}` | `api-key` | Delete a job |
| POST | `/api/abyssal/crawl/jobs/{id}/pause` | `api-key` | Pause a job |
| POST | `/api/abyssal/crawl/jobs/{id}/resume` | `api-key` | Resume a job |
| POST | `/api/abyssal/crawl/jobs/{id}/rerun` | `api-key` | Rerun a job |
| POST | `/api/abyssal/wayback/capture` | `api-key` | Capture a single snapshot |

### Crawler

- **Concurrency**: 1–20 workers via `asyncio.Semaphore` (configurable per job)
- **Delay**: 0–60s per-worker delay after each request, applied **outside** the semaphore
- **URL normalization at start**: the `/crawl/start` endpoint and the Admin UI both normalize seed URLs — bare hostnames get `http://` prepended and `.i2p` appended (e.g. `identiguy` → `http://identiguy.i2p`). The frontend shows a live preview when the input differs from the normalized form.
- **URL normalization**: canonical URLs (lowercase, strip fragments, remove default ports, collapse `//`/`./`/`../`, sort query params)
- **Retry logic**: 3 attempts with exponential backoff (1s → 2s → 4s) for 5xx, 429, timeouts, connection errors
- **Robots.txt**: fetched per-domain, 24h cache, respects `Disallow` and `Crawl-delay`
- **429 backoff**: reads `Retry-After` header, stores domain-level rate-limit window
- **Per-domain rate limiting**: minimum interval (default 1s) between requests to same domain
- **b32/AH resolution**: jump service chain (stats.i2p → notbob.i2p → reg.i2p); successful resolves cached, failures retried
- **Language detection**: 14 languages — HTML lang attr, charset, Unicode script ranges, stopword frequency
- **Site type detection**: 18 types — generator patterns, URL paths, content keywords, OG types, nav analysis
- **Auto-recrawl scheduler**: 24h loop, unlimited crawl jobs for previously-seen hostnames
- **Auto-spawn**: discovering new `.i2p` hosts on a crawled page auto-creates new crawl jobs
- **Registry address book crawler**: fetches hosts.txt from known registries (reg.i2p, notbob.i2p, stats.i2p, inr.i2p, i2pd.i2p) and adds entries to site_status; runs every 6 hours; auto-discovers new registry sources (e.g. bigrat.i2p, /export/alive-hosts.txt)
- **Wayback integration**: every crawled HTML page creates a Wayback snapshot

### Wayback Machine

- **Storage**: Filesystem by hostname (`/data/archive/{hostname}/{timestamp}_{status}_{sha256}.html`)
- **CSS inlining**: fetches external stylesheets through the I2P proxy at capture time
- **URL rewriting**: view-time rewriting of images/scripts/fonts through the Prism browser proxy
- **Scheduled re-capture**: per-URL configurable interval
- **Search**: by URL or title

### Crawler DB (`abyssal/abyssal/crawler/db.py`)

- SQLite with WAL mode for concurrent access
- Tables: `crawl_jobs`, `crawled_pages`, `crawl_queue`, `site_status`, `site_links`, `registry_sources`
- FTS5 virtual table `pages_fts` with porter+unicode61 tokenizer
- Fields indexed: title, content, description, keywords

### Classifier (`abyssal/abyssal/classifier/classify.py`)

Language detection order:
1. `<html lang>` attribute
2. `<meta http-equiv="content-language">`
3. `<meta name="language">`
4. Charset detection (15 charset→language mappings)
5. Unicode script range detection (Cyrillic, Japanese, Chinese, Arabic, Korean, Thai, Greek, Hebrew, Devanagari)
6. Stopword frequency analysis (11 Latin-script languages)

Site type detection order:
1. `<meta name="generator">` patterns (WordPress→blog, phpBB→forum, etc.)
2. URL path patterns (`/forum/`, `/wiki/`, `/shop/`, etc.)
3. Open Graph type
4. Content keyword analysis
5. `<nav>` element analysis

### Resolver (`abyssal/abyssal/resolver/resolver.py`)

- Tries 3 I2P jump services in sequence
- Computes b32 address from base64 destination hash
- Returns `{b32, address_helper}` on success

---

## Prism — Dashboard + Browser + Addressbook

### Endpoints

| Route | Service | Purpose |
|-------|---------|---------|
| `GET /api/health` | Router | Composite health score (0–100) |
| `GET /api/status` | Router | Network status, uptime, peers |
| `GET /api/bandwidth` | Router | Inbound/outbound rates |
| `GET /api/tunnels` | Router | Tunnel list with state/direction |
| `GET /api/router-info` | Router | Router identity, version, flags |
| `GET /api/commands` | Router | i2pd control commands |
| `GET /api/transports` | Router | Transport information |
| `GET /api/local-destinations` | Router | Local I2P destinations |
| `GET /api/browser/proxy` | Browser | Fetch `.i2p` URL through i2pd proxy |
| `GET /api/browser/bookmarks` | Browser | List bookmarks |
| `POST /api/browser/bookmarks` | Browser | Add bookmark |
| `DELETE /api/browser/bookmarks/{id}` | Browser | Remove bookmark |
| `GET /api/addressbook/subscriptions` | Addressbook | List subscriptions |
| `POST /api/addressbook/subscribe` | Addressbook | Add subscription |
| `POST /api/addressbook/unsubscribe` | Addressbook | Remove subscription |

### Frontend

- **Stack**: Minimal vanilla HTML/CSS/JS served through nginx
- **Routing**: Path-based (direct nginx `try_files $uri /index.html` fallback)
- **Pages**: Search (`/`), Directory (`/browse`), Site Detail (`/site/{hostname}`), Wayback (`/wayback`), Address Book (`/addressbook`)
- **API calls**: `window.fetch()` with helper `api()` function
- **Single file app**: `index.html` + `style.css` + `app.js` under `frontend/client/static/`
- **Build**: Docker copies `static/` dir into nginx image (no Node.js needed)
- **Key features**: Search with language/site_type filters, pagination, folder tree view, status badges, hosts.txt export display

### Frontend pages

- `/` — Dashboard: health gauge, status, bandwidth, tunnel manager, router info
- `/browser` — Tabbed I2P browser with bookmarks and JS toggle
- `/addressbook` — Subscription management

---

## SAM Tunnel Service

- Python 3.11 service at `prism/i2pd/abyssal-tunnel/tunnel.py` connecting to i2pd SAM on port 7656
- Creates streaming sessions for abyssal (port 80) and abyssal-api (port 8000) destinations
- Uses unique session IDs (`tun_{name}_{ts}_{rand}`) to avoid `DUPLICATED_ID`
- Computes b32 addresses: base64-decode → SHA-256 → base32-encode
- Runs in Docker at 172.18.0.10 with `abyssal-data` volume

## Dev Commands

```sh
# Start everything
cd abyssal && docker compose up --build

# Rebuild a single service
docker compose up --build -d abyssal-backend

# View logs
docker compose logs -f abyssal-backend
docker compose logs -f prism-router
docker compose logs -f abyssal-tunnel

# Run prism backend tests
cd prism/backend && python3 test_api.py
```

## Conventions

- After completing a task, update docs before concluding: `AGENTS.md` (this file) for cross-project context, `prism/AGENTS.md` or `prism/SESSION_PROMPT.md` for Prism-specific changes.
- Dark mode by default (gradient background `#0a1628` → `#0d1117`).
- API key header: Abyssal uses `api-key`, Prism uses `x-api-key`. Both default to `dev-key-12345`.
- `.env` lives in `abyssal/` and is shared by all services via `env_file: .env`.
- nginx config at `abyssal/nginx/default.conf` — changes need `docker compose restart nginx`.
- Volume data persists in Docker volumes `abyssal-data` and `i2pd-data`.
- Abyssal frontend is vanilla HTML/CSS/JS (no framework) — `frontend/client/static/`.
- I2PControl: `Token` param included in **all** JSON-RPC calls after `Authenticate` (i2pd v2.60.0 requires it).

## Pre-Commit Checklist

Run these checks before every commit to catch regressions early. If a check fails, fix before committing.

### 0. Update ALL Documents

Update **all** documents in the repo before committing:
- `AGENTS.md` (this file) — cross-project changes
- `prism/AGENTS.md` — Prism-specific changes
- `prism/SESSION_PROMPT.md` — Prism session context
- `prism/PROJECT_SUMMARY.md` — Prism architecture summary
- `prism/FILE_MANIFEST.md` — Prism file inventory
- Any other `.md` files affected by the change

### 1. Build

```sh
# From abyssal/ — builds all project containers
docker compose build abyssal-frontend abyssal-backend abyssal-tunnel prism-frontend prism-router prism-browser prism-addressbook nginx

# From prism/ — also needed for standalone prism services
docker compose build api-router api-browser api-addressbook frontend nginx
```

### 2. Container Health

```sh
docker compose ps --status running          # all 8 containers: Up
docker compose logs abyssal-tunnel --tail 5  # SAM sessions: RESULT=OK for both tunnels
docker compose logs nexus-i2pd-1 --tail 20   # no LeaseSet/Publish errors
```

### 3. I2P Router & Eepsite

```sh
# Router status — confirms I2PControl Token fix works, network is online
curl -s -H "x-api-key: dev-key-12345" http://localhost/api/status
# Expect: "status":"online", active_peers > 0, tunnel_count > 0

# Router health — composite score
curl -s -H "x-api-key: dev-key-12345" http://localhost/api/router-health
# Expect: health_score > 0, network.routers_known > 0

# SAM tunnel — both eepsite destinations created successfully
docker logs nexus-abyssal-tunnel-1 2>&1 | grep "RESULT=OK"
# Expect: 2 lines, one for abyssal and one for abyssal-api

# Eepsite b32 addresses (search engine + API)
docker logs nexus-abyssal-tunnel-1 2>&1 | grep "\.b32\.i2p"
# Expect: 2 lines with *.b32.i2p addresses

# LeaseSet — no publish failures
docker logs nexus-i2pd-1 2>&1 | grep -i "Publish confirmation was not received"
# Expect: empty (no output = no errors)
```

**Eepsite reachability checklist:**
- [ ] SAM tunnel logs show `RESULT=OK` for both `abyssal` and `abyssal-api` sessions
- [ ] Two `*.b32.i2p` addresses appear in the tunnel logs
- [ ] Eepsite responds via I2P browser proxy (get the b32 from logs first):
  ```sh
  B32=$(docker logs nexus-abyssal-tunnel-1 2>&1 | grep "\.b32\.i2p" | head -1 | grep -oE '[a-z2-7]+\.b32\.i2p')
  curl -s -H "x-api-key: dev-key-12345" "http://localhost/api/browser/proxy?url=http://${B32}"
  # Expect: non-empty HTML from the eepsite
  ```
- [ ] No LeaseSet publish failures in i2pd logs

### 4. Abyssal Search Engine — API

```sh
# Search (FTS5) — public endpoint
curl -s http://localhost/api/abyssal/search?q=test
# Expect: JSON with results array, total > 0 (should have crawled data)

# Facets — available languages and site types
curl -s http://localhost/api/abyssal/facets
# Expect: JSON with languages and site_types arrays

# Directory — discovered sites
curl -s http://localhost/api/abyssal/sites
# Expect: JSON with sites array (may be empty)

# Site link graph
curl -s http://localhost/api/abyssal/graph
# Expect: JSON with nodes + edges arrays

# Wayback stats
curl -s http://localhost/api/abyssal/wayback/stats
# Expect: JSON with archive stats (totals, etc.)
```

### 5. Abyssal Crawler — API + Verification

**Crawler behavior rules (enforced in `worker.py` and `main.py`):**
- A job that finishes with `pages_crawled == 0` is marked **`failed`**, never `completed`.
- Completed jobs are hidden behind a **"Show completed jobs"** toggle in the Admin UI.
- **Seeding only happens on a genuinely empty database** (zero jobs of any kind). Restarting an existing DB is always a no-op for the seeder. If seed jobs fail because i2pd wasn't ready, rerun them manually from the Admin UI — the seeder will not retry on its own.
- Seeds fire 120 s after startup (background task) to give i2pd time to bootstrap.

```sh
# List all crawl jobs
curl -s -H "api-key: dev-key-12345" http://localhost/api/abyssal/crawl/jobs
# Expect: JSON array; seed URLs (notbob, stats, reg, i2pd) present on fresh DB

# No completed job should ever have 0 pages (invariant check)
curl -s -H "api-key: dev-key-12345" http://localhost/api/abyssal/crawl/jobs | \
  python3 -c "import sys,json; bad=[j for j in json.load(sys.stdin) if j['status']=='completed' and j['pages_crawled']==0]; print('BAD:',bad) if bad else print('OK')"
# Expect: OK

# Auto-spawn check — after notbob/stats crawl, many child jobs should exist
curl -s -H "api-key: dev-key-12345" http://localhost/api/abyssal/crawl/jobs | \
  python3 -c "import sys,json; jobs=json.load(sys.stdin); print(len(jobs),'total jobs')"
# Expect: well more than 4 after any seed crawl completes (auto-spawn creates child jobs)

# crawl_queue drains to zero once a job finishes (regression check for infinite-loop bug)
docker exec nexus-abyssal-backend-1 \
  python3 -c "import asyncio,aiosqlite; async def r(): db=await aiosqlite.connect('/data/crawler.db'); r=await db.execute_fetchall('SELECT job_id,COUNT(*) c FROM crawl_queue GROUP BY job_id'); [print(row) for row in r]; await db.close(); asyncio.run(r())"
# Expect: empty output (or only rows for actively running jobs)

# Seed URL duplicate check — each seed should appear only once across all jobs
curl -s -H "api-key: dev-key-12345" http://localhost/api/abyssal/crawl/jobs | \
  python3 -c "
import sys,json
from collections import Counter
jobs=json.load(sys.stdin)
seeds=['http://notbob.i2p','http://stats.i2p','http://reg.i2p','http://i2pd.i2p']
counts=Counter(j['url'] for j in jobs if j['url'] in seeds)
print('OK' if all(v==1 for v in counts.values()) else 'DUPLICATES:'+str(dict(counts)))
"
# Expect: OK  (restart must not create extra seed jobs)
```

**Crawler/Wayback integration checklist:**
- [ ] After a crawl job completes with pages > 0, `wayback/stats` shows `total_snapshots > 0`
- [ ] `wayback/urls` lists at least one URL from the crawled site
- [ ] Snapshot files actually exist on disk (not just in DB):
  ```sh
  docker exec nexus-abyssal-backend-1 \
    python3 -c "
import asyncio, aiosqlite, os
async def r():
    db = await aiosqlite.connect('/data/crawler.db')
    rows = await db.execute_fetchall('SELECT file_path FROM wayback_snapshots LIMIT 5')
    for row in rows:
        exists = os.path.exists(row['file_path'])
        print('OK' if exists else 'MISSING', row['file_path'])
    await db.close()
asyncio.run(r())
"
  # Expect: all lines start with OK
  ```
- [ ] Snapshot viewer renders a real page (pick any ID from `wayback/stats` recent_snapshots):
  ```sh
  ID=$(curl -s http://localhost/api/abyssal/wayback/stats | python3 -c "import sys,json; s=json.load(sys.stdin); print(s['recent_snapshots'][0].get('id',''))" 2>/dev/null)
  curl -s "http://localhost/api/abyssal/wayback/snapshots/${ID}/view" | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if d.get('content') else 'EMPTY')"
  # Expect: OK
  ```
- [ ] `/api/abyssal/archive` directory exists and contains subdirectories:
  ```sh
  docker exec nexus-abyssal-backend-1 ls /data/archive/
  # Expect: one directory per crawled hostname
  ```

### 5.5 Abyssal Eepsite — SAM Tunnel Info

```sh
# Eepsite endpoint returns b32 addresses for both SAM tunnels
curl -s http://localhost/api/abyssal/eepsite | python3 -c "import sys,json; t=json.load(sys.stdin)['tunnels']; print(len(t),'tunnels'); [print(n['name'],n['b32_address']) for n in t]"
# Expect: 2 tunnels, each with a *.b32.i2p address
```

### 5.6 Dashboard — Eepsite Card + Bandwidth Letter Presets

Dashboard shows:
- **Eepsite card**: displays in the Router Info grid, shows abyssal + abyssal-api b32 addresses with collapsible
- **Bandwidth letter presets**: K(16), L(32), M(64), N(128), O(256), P(512), X(1024) buttons replace raw KB/s inputs; auto mode maps slow-2g→K, 2g→L, 3g→N, 4g→P

### 6. Prism Dashboard — API + Frontend

```sh
# Dashboard frontend loads
curl -s -o /dev/null -w "%{http_code}" http://localhost/dashboard/
# Expect: 200

# Router info (used by dashboard info cards)
curl -s -H "x-api-key: dev-key-12345" http://localhost/api/router-info
# Expect: JSON with version, identity, uptime, net_id

# Bandwidth (used by bandwidth card + chart)
curl -s -H "x-api-key: dev-key-12345" http://localhost/api/bandwidth
# Expect: JSON with inbound_rate, outbound_rate

# Tunnel list (used by tunnel manager)
curl -s -H "x-api-key: dev-key-12345" http://localhost/api/tunnels
# Expect: JSON with tunnels array + total

# Router details (used by identity, contribution, services cards)
curl -s -H "x-api-key: dev-key-12345" http://localhost/api/router-details
# Expect: JSON with identity, caps, version, services, etc.

# Transports
curl -s -H "x-api-key: dev-key-12345" http://localhost/api/transports
# Expect: JSON with transports array

# Local I2P destinations
curl -s -H "x-api-key: dev-key-12345" http://localhost/api/local-destinations
# Expect: JSON with destinations array

# Commands (i2pd control)
curl -s -H "x-api-key: dev-key-12345" http://localhost/api/commands
# Expect: JSON with commands array
```

### 7. Prism Browser — API

```sh
# Bookmark list
curl -s -H "x-api-key: dev-key-12345" http://localhost/api/browser/bookmarks
# Expect: JSON with bookmarks array

# Add a bookmark (cleanup: delete it after)
curl -s -X POST -H "x-api-key: dev-key-12345" -H "Content-Type: application/json" \
  -d '{"name":"Test","url":"http://test.i2p"}' \
  http://localhost/api/browser/bookmarks
# Expect: 200 or 201, bookmark created

# Delete the test bookmark
# curl -s -X DELETE -H "x-api-key: dev-key-12345" http://localhost/api/browser/bookmarks/1
```

### 8. Prism Addressbook — API

```sh
# List subscriptions
curl -s -H "x-api-key: dev-key-12345" http://localhost/api/addressbook/subscriptions
# Expect: JSON with subscriptions array

# Subscribe (add a subscription)
# curl -s -X POST -H "x-api-key: dev-key-12345" -H "Content-Type: application/json" \
#   -d '{"url":"http://example.i2p/subscriptions.txt"}' \
#   http://localhost/api/addressbook/subscribe
```

### 9. Abyssal Frontend — Search Engine SPA

```sh
curl -s -o /dev/null -w "%{http_code}" http://localhost/
# Expect: 200 (Abyssal search SPA loads)

curl -s http://localhost/ | grep -o "search\|Search\|abyssal\|Abyssal"
# Expect: non-empty — page contains search-related content
```

**Crawler Admin UI checklist (`/admin`):**
- [ ] Active jobs (running/pending/paused/failed) visible immediately in the main list
- [ ] Completed jobs hidden by default behind "Show completed jobs" button
- [ ] Clicking the button reveals the collapsed completed jobs section
- [ ] Completed jobs badge shows correct count
- [ ] Pause/resume/rerun/delete buttons work correctly per job status

### 10. Prism Dashboard — Full-Stack Integration

```sh
# Composite: frontend HTML loads AND its API calls succeed
# The dashboard polls /api/status every 1s — check that it returns data
curl -s -H "x-api-key: dev-key-12345" http://localhost/api/status | grep -o "online"
# Expect: "online"

# Dashboard SPA references working API endpoints
# Health endpoint (should now return 200, was 404 before nginx fix)
curl -s http://localhost/api/health
# Expect: {"status":"ok","timestamp":"..."}
```

### 11. Git Hygiene

- [ ] No secrets committed: `git diff --cached` shows no real API keys, passwords, or certs
- [ ] No stale lock files: `package-lock.json` deleted if `pnpm-lock.yaml` exists
- [ ] `AGENTS.md` updated with new conventions, services, or commands
- [ ] Docs updated (`prism/SESSION_PROMPT.md`, `prism/AGENTS.md`) for Prism-specific changes
- [ ] Commit message matches repo style (concise, prefixed by subsystem if applicable)

### 12. Abyssal — Archive, FTS5, Graph, i2pd Proxy, Error Log

```sh
# ── Snapshot files exist on disk (catches ARCHIVE_ROOT str-vs-Path bug) ───────
docker exec nexus-abyssal-backend-1 python3 - <<'EOF'
import asyncio, aiosqlite, os
async def r():
    db = await aiosqlite.connect("/data/crawler.db")
    db.row_factory = aiosqlite.Row
    rows = await db.execute_fetchall("SELECT file_path FROM wayback_snapshots LIMIT 20")
    if not rows:
        print("No snapshots in DB yet")
    else:
        missing = [r["file_path"] for r in rows if not os.path.exists(r["file_path"])]
        print("MISSING:", missing if missing else "none — all files present on disk")
    await db.close()
asyncio.run(r())
EOF
# Expect: MISSING: none — all files present on disk

# ── FTS5 row count matches crawled_pages (index in sync) ─────────────────────
docker exec nexus-abyssal-backend-1 python3 - <<'EOF'
import asyncio, aiosqlite
async def r():
    db = await aiosqlite.connect("/data/crawler.db")
    db.row_factory = aiosqlite.Row
    pages = (await db.execute_fetchall("SELECT COUNT(*) AS n FROM crawled_pages"))[0]["n"]
    fts   = (await db.execute_fetchall("SELECT COUNT(*) AS n FROM pages_fts"))[0]["n"]
    status = "OK" if pages == fts else "MISMATCH — FTS index out of sync"
    print(f"crawled_pages={pages}  pages_fts={fts}  {status}")
    await db.close()
asyncio.run(r())
EOF
# Expect: counts identical

# ── FTS5 search actually returns results (not just HTTP 200 with empty array) ──
curl -s "http://localhost/api/abyssal/search?q=i2p" \
  | python3 -c "import sys,json; r=json.load(sys.stdin); print('total:', r['total'], '| OK' if r['total'] > 0 else '| NO RESULTS — crawl first')"
# Expect: total > 0

# ── Link graph populated after a crawl ────────────────────────────────────────
curl -s http://localhost/api/abyssal/graph \
  | python3 -c "import sys,json; g=json.load(sys.stdin); print('nodes:', len(g['nodes']), '| links:', len(g['links']))"
# Expect: nodes > 1, links > 0 (auto-spawn creates many child nodes)

# ── i2pd HTTP proxy reachable from INSIDE the backend container ───────────────
# If this fails, no crawling is possible regardless of i2pd's own status
docker exec nexus-abyssal-backend-1 python3 - <<'EOF'
import urllib.request, urllib.error
proxy  = urllib.request.ProxyHandler({"http": "http://i2pd:4444"})
opener = urllib.request.build_opener(proxy)
try:
    resp = opener.open("http://notbob.i2p", timeout=30)
    print(f"OK — HTTP {resp.status}")
except urllib.error.HTTPError as e:
    print(f"OK — HTTP {e.code} (proxy routing, eepsite returned error code)")
except Exception as e:
    print(f"FAIL — {e}")
EOF
# Expect: OK  (any HTTP status is fine; exception = proxy itself is unreachable)

# ── No ERROR-level log entries in the backend ─────────────────────────────────
docker logs nexus-abyssal-backend-1 2>&1 | grep " ERROR " | tail -10
# Expect: empty (investigate any lines that appear)

# ── Scheduler and seeder started correctly ────────────────────────────────────
docker logs nexus-abyssal-backend-1 2>&1 | grep -E "scheduler|seed|fresh database"
# Expect:
#   "Auto-recrawl scheduler started (check every 300s, recrawl after 24h, jitter up to 3600s)"
#   AND one of:
#   "Fresh database — seeding N crawl job(s) after 120s delay"  (first boot)
#   "Database already has N job(s) — skipping seed (not a fresh DB)"  (subsequent boots)
```

### 13. Public Addressbook

```sh
# Addressbook endpoint returns data — no auth required (intentionally public)
curl -s "http://localhost/api/abyssal/addressbook" \
  | python3 -c "import sys,json; r=json.load(sys.stdin); print('total:', r['total'])"
# Expect: total > 0 after any crawl has run

# hosts.txt line format check
curl -s "http://localhost/api/abyssal/addressbook?per_page=5" \
  | python3 -c "
import sys, json
for s in json.load(sys.stdin)['sites']:
    if s['b32']:
        b32 = s['b32'] if s['b32'].endswith('.b32.i2p') else s['b32'] + '.b32.i2p'
        print(f\"{s['hostname']}={b32}\")
"
# Expect: one hostname=*.b32.i2p line per resolved site

# Addressbook page loads in browser (SPA route)
curl -s -o /dev/null -w "%{http_code}" http://localhost/addressbook
# Expect: 200

### 14. Registry Address Book Crawler

```sh
# Seed registries present
docker exec nexus-abyssal-backend-1 python3 -c "
import asyncio, aiosqlite
async def r():
    db = await aiosqlite.connect('/data/crawler.db')
    db.row_factory = aiosqlite.Row
    rows = await db.execute_fetchall('SELECT url, last_fetched, entries_found FROM registry_sources')
    for r in rows: print(r['url'], '| last_fetched:', r['last_fetched'] or 'never', '| entries:', r['entries_found'])
    await db.close()
asyncio.run(r())
"
# Expect: at least 6 seed registries; some with entries_found > 0 after first cycle

# Auto-discovery added new registry URLs (bigrat.i2p, /export/alive-hosts.txt, etc.)
docker exec nexus-abyssal-backend-1 python3 -c "
import asyncio, aiosqlite
async def r():
    db = await aiosqlite.connect('/data/crawler.db')
    rows = await db.execute_fetchall('SELECT url FROM registry_sources WHERE url NOT IN (?,?,?,?,?,?) ORDER BY url', ['http://reg.i2p/hosts.txt','http://notbob.i2p/hosts.txt','http://stats.i2p/hosts.txt','http://inr.i2p/hosts.txt','http://inr.i2p/contacts/','http://i2pd.i2p/hosts.txt'])
    print('Auto-discovered' if rows else 'No new discoveries yet')
    for r in rows: print(' ', r['url'])
    await db.close()
asyncio.run(r())
"
# Expect: auto-discovered entries like http://bigrat.i2p/hosts.txt, http://inr.i2p/export/alive-hosts.txt

# Hosts from registry appear in addressbook
curl -s http://localhost/api/abyssal/addressbook | python3 -c "import sys,json; r=json.load(sys.stdin); print('total:', r['total'])"
# Expect: total > 0 (entries from registry added to site_status)
```

## Testing

See [PRECOMMIT.md](PRECOMMIT.md) for the full pre-commit checklist.

### Quick Test Commands

```sh
# Run all tests (requires services running)
cd ~/Developer/nexus
python -m pytest tests/ -v

# Offline unit tests (no services needed)
abyssal/.venv/bin/python -m pytest tests/abyssal/test_unit.py tests/prism/test_browser_unit.py

# Integration suites against local services instead of Docker
ABYSSAL_URL=http://127.0.0.1:8000 python -m pytest tests/abyssal/test_api.py
PRISM_ROUTER_URL=... PRISM_BROWSER_URL=... PRISM_ADDRESSBOOK_URL=... python -m pytest tests/prism/test_api.py
```

### Test Files
- `tests/abyssal/test_api.py` — 27 integration tests for Abyssal API (search, directory, wayback, addressbook, crawler admin)
- `tests/prism/test_api.py` — 32 integration tests for Prism API (router, browser, addressbook, error handling)
- `tests/abyssal/test_unit.py` — offline tests for FTS query building, snippet escaping, hostname SQL, snapshot storage, URL rewriting
- `tests/prism/test_browser_unit.py` — offline tests for browser proxy token auth and sandbox headers

### Browser proxy auth
- `/api/browser/proxy` accepts the `x-api-key` header, `?token=BROWSER_TOKEN` (any host), or `?token=PROXY_TOKEN` (`.i2p` only).
- Both tokens are HMAC-derived from `API_KEY` unless set explicitly. Never put `API_KEY` in a URL or in rewritten HTML.
- Abyssal page/snapshot views embed `PROXY_TOKEN`; the Prism dashboard fetches `BROWSER_TOKEN` from `GET /api/browser/token`.
- Proxied responses carry `Content-Security-Policy: sandbox ...` so third-party scripts run in an opaque origin.
