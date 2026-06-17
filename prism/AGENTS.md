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
- Python backend in `backend/services/*/` (3 microservices: router, browser, addressbook)
- Routes: `/api/router/*` → api-router, `/api/browser/*` → api-browser, `/api/addressbook/*` → api-addressbook (crawler/wayback moved to Abyssal monorepo)
- Backend proxies i2pd JSON-RPC API
- Dark-mode Tailwind CSS UI
- shadcn/ui component patterns
- All API calls use `x-api-key` header; view endpoints also accept `api_key` query param
- Dev key: `dev-key-12345`

## Key Features (recent additions)
- **Parallel crawlers**: `concurrency` field (1-20 workers), uses `asyncio.Semaphore` *(in Abyssal)*
- **Crawl speed control**: `delay_seconds` field (0-60s delay per worker after each request) *(in Abyssal)*
- **Crawler 0-page guard**: jobs that finish with 0 pages crawled are automatically marked `failed` *(in Abyssal `worker.py`)*
- **Completed jobs UI**: Admin page hides completed jobs behind a collapsible "Show completed jobs" button *(in Abyssal frontend `AdminPage.tsx`)*
- **b32/AH resolution**: jump service chain (stats.i2p → notbob.i2p → reg.i2p); failures retried (not cached) *(in Abyssal)*
- **Language detection**: 14 languages — checks HTML lang, charset, Unicode script ranges, stopword frequency *(in Abyssal)*
- **Site type detection**: 18 types — generator patterns, URL paths, content keywords, OG types, nav analysis *(in Abyssal)*
- **Delete confirmation**: warns that Wayback snapshots are preserved *(in Abyssal)*
- **Router health gauge**: auto-scaling bandwidth (B/s, KB/s, MB/s, GB/s) via `formatBps()`
- **Wayback view endpoint**: accepts `api_key` query param for "Open in new tab" *(in Abyssal)*
- **Crawler view endpoint**: `GET /api/abyssal/pages/{id}/view` with URL rewriting *(in Abyssal)*
- **Iframe previews**: use backend view endpoints (not blob URLs) with `sandbox="allow-same-origin allow-scripts"`
- **Eepsite card**: Dashboard shows Abyssal eepsite b32 addresses (SAM tunnel tunnels) with collapsible b32 display
- **Bandwidth letter presets**: K/L/M/N/O/P/X presets replacing raw KB/s number inputs; auto mode maps connection type to letter
- **SAM tunnel writes info JSON**: `/data/tunnel-info.json` with name, b32 address, host/port for each tunnel; shared via `abyssal-data` volume
