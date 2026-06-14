# Prism — Agent Guide

## Overview
Prism is a web dashboard for monitoring i2pd routers. Stack: React 19 + Vite + Tailwind CSS (frontend), Python FastAPI (backend), Docker Compose (infrastructure).

## Dev Servers (Docker Compose)

```sh
# Start everything with hot-reload (dev override)
docker compose up --build

# Production mode (no dev override)
docker compose -f docker-compose.yml up --build
```

## Commands

```sh
# Rebuild a single service
docker compose up --build -d <service-name>

# View logs
docker compose logs -f <service-name>

# Run backend tests
cd backend && python3 test_api.py

# Install local deps (if developing outside Docker)
cd backend && pip3 install -r requirements.txt
cd frontend/client && pnpm install
```

## Conventions
- After completing any task, update relevant docs (`SESSION_PROMPT.md` for features, `PROJECT_SUMMARY.md` for architecture, `FILE_MANIFEST.md` for new files) before concluding.
- TypeScript/React frontend in `frontend/client/`
- Python backend in `backend/services/*/` (6 microservices)
- Routes: `/api/router/*` → api-router, `/api/browser/*` → api-browser, `/api/crawler/*` → api-crawler, `/api/wayback/*` → api-wayback, `/api/addressbook/*` → api-addressbook
- Backend proxies i2pd JSON-RPC API
- Dark-mode Tailwind CSS UI
- shadcn/ui component patterns
- All API calls use `x-api-key` header; view endpoints also accept `api_key` query param
- Dev key: `dev-key-12345`

## Key Features (recent additions)
- **Parallel crawlers**: `concurrency` field (1-20 workers), uses `asyncio.Semaphore`
- **Crawl speed control**: `delay_seconds` field (0-60s delay per worker after each request)
- **b32/AH resolution**: jump service chain (stats.i2p → notbob.i2p → reg.i2p); failures retried (not cached)
- **Language detection**: 14 languages — checks HTML lang, charset, Unicode script ranges, stopword frequency
- **Site type detection**: 18 types — generator patterns, URL paths, content keywords, OG types, nav analysis
- **Delete confirmation**: warns that Wayback snapshots are preserved
- **Router health gauge**: auto-scaling bandwidth (B/s, KB/s, MB/s, GB/s) via `formatBps()`
- **Wayback view endpoint**: accepts `api_key` query param for "Open in new tab"
- **Crawler view endpoint**: `GET /api/crawler/pages/{id}/view` with URL rewriting
- **Iframe previews**: use backend view endpoints (not blob URLs) with `sandbox="allow-same-origin allow-scripts"`
