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
| Frontend | React 19 + TypeScript 6 + Vite 8 + Tailwind CSS 4 + shadcn/ui + wouter |
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
- **Wayback integration**: every crawled HTML page creates a Wayback snapshot

### Wayback Machine

- **Storage**: Filesystem by hostname (`/data/archive/{hostname}/{timestamp}_{status}_{sha256}.html`)
- **CSS inlining**: fetches external stylesheets through the I2P proxy at capture time
- **URL rewriting**: view-time rewriting of images/scripts/fonts through the Prism browser proxy
- **Scheduled re-capture**: per-URL configurable interval
- **Search**: by URL or title

### Crawler DB (`abyssal/abyssal/crawler/db.py`)

- SQLite with WAL mode for concurrent access
- Tables: `crawl_jobs`, `crawled_pages`, `crawl_queue`, `site_status`, `site_links`
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
- Dark mode by default (Tailwind CSS v4, `oklch(0.141 0.005 285.823)` background).
- shadcn/ui patterns: `cn()` utility, named exports from `@/components/ui/*`.
- API key header: Abyssal uses `api-key`, Prism uses `x-api-key`. Both default to `dev-key-12345`.
- `.env` lives in `abyssal/` and is shared by all services via `env_file: .env`.
- nginx config at `abyssal/nginx/default.conf` — changes need `docker compose restart nginx`.
- Volume data persists in Docker volumes `abyssal-data` and `i2pd-data`.
- Dependencies managed via pnpm; delete stale `package-lock.json` files. Frontend package bumps need `pnpm install` regen.
- I2PControl Token param removed from non-Authenticate calls (i2pd v2.60.0 rejects it).
- Security fixes: python-dotenv bumped to 1.2.2 (CVE-2024-28180), esbuild via Vite 8 upgrade (GHSA-67mh-4wv8-2f99).

## Pre-Commit Checklist

Run these checks before every commit to catch regressions early. If a check fails, fix before committing.

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

### 4. Abyssal Search Engine — API

```sh
# Search (FTS5) — public endpoint
curl -s http://localhost/api/abyssal/search?q=test
# Expect: JSON with results array (may be empty if no crawled data)

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

### 5. Abyssal Crawler — API

```sh
# List crawl jobs
curl -s -H "api-key: dev-key-12345" http://localhost/api/abyssal/crawl/jobs
# Expect: JSON with jobs array, status 200

# Start a crawl job (optional — only run if you want to actually crawl)
# curl -s -X POST -H "api-key: dev-key-12345" -H "Content-Type: application/json" \
#   -d '{"seed":"http://example.i2p","max_pages":5,"depth":1}' \
#   http://localhost/api/abyssal/crawl/start
```

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
