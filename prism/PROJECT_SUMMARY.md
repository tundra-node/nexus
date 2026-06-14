# Prism — Project Summary

## Overview

Prism is a containerized web dashboard for monitoring and browsing I2P sites via an i2pd router. It runs 7 Docker services (6 Python microservices + React frontend) behind an nginx reverse proxy, with an i2pd router in a separate container.

## Technology Stack

### Backend (6 microservices)

| Service | Framework | Port | Purpose |
|---------|-----------|------|---------|
| api-router | FastAPI + httpx | 8001 | Proxies i2pd JSON-RPC + I2PControl |
| api-browser | FastAPI + httpx + BeautifulSoup | 8002 | I2P HTTP proxy with link rewriting |
| api-crawler | FastAPI + aiosqlite + httpx + BeautifulSoup | 8003 | Web crawler with parallel workers |
| api-wayback | FastAPI + aiosqlite + httpx + BeautifulSoup | 8004 | Wayback Machine capture/replay |
| api-addressbook | FastAPI + aiosqlite + httpx | 8005 | Addressbook subscription management |

### Frontend

| Component | Technology | Version |
|-----------|------------|---------|
| Framework | React | 19 |
| Styling | Tailwind CSS | 4 |
| Build | Vite | 6 |
| Routing | Wouter | 3 |
| UI Components | shadcn/ui | Latest |
| Icons | Lucide React | 0.453 |
| Notifications | Sonner | 2 |

### Infrastructure

| Component | Technology |
|-----------|------------|
| Reverse Proxy | nginx (with resolver 127.0.0.11 for Docker DNS) |
| I2P Router | purplei2p/i2pd:latest |
| Orchestration | Docker Compose |
| Volumes | wayback-data, i2pd-data |
| Python | 3.11-slim (all services) |

## Core Features

### 1. Router Health Dashboard
- 0-100 health score with circular SVG gauge (color-coded: green ≥70, amber ≥40, red <40)
- Real-time status badges (Online/Offline) with Floodfill and Reachable flags
- Metrics grid: active peers, total tunnels, known routers, tunnel success rate
- Auto-scaling bandwidth display (B/s, KB/s, MB/s, GB/s)

### 2. I2P Browser
- Proxies `.i2p` sites through i2pd HTTP proxy (port 4444)
- Inline link rewriting so navigation stays within the proxy
- Tabbed browsing with back/forward navigation
- Bookmark management (persisted to `/data/browser_bookmarks.json`)
- JavaScript toggle per tab

### 3. Addressbook
- Subscribe to remote hosts files (reg.i2p, stats.i2p)
- Parser handles both CSV and reg.i2p `=`-separated format
- Writes subscriptions to i2pd.conf on the i2pd-data volume

### 6. Router Health Endpoint
- `GET /api/router-health` returns a composite health score (0-100)
- Computed from: network status, peer count, tunnel success rate, bandwidth activity
- Returns detailed breakdown: uptime, peers, tunnels, bandwidth, network status, floodfill/reachable flags

## API Architecture

### Authentication
All endpoints require `x-api-key` header. Some also accept `api_key` query parameter:
- Browser proxy: `GET /api/browser/proxy?url=&api_key=`
- Wayback view: `GET /api/wayback/snapshots/{id}/view?api_key=`
- Crawler view: `GET /api/crawler/pages/{id}/view?api_key=`
- Browser proxy rewritten URLs: `api_key` embedded in URL

### Endpoint Summary

**Router Dashboard** (7 endpoints): health, status, bandwidth, tunnels, router info, commands, transports, local destinations

**Browser** (3 endpoints): proxy fetch, bookmarks CRUD

**Crawler** (11 endpoints): start job, list/get/delete jobs, pause/resume, rerun, search pages, view page, site status

**Wayback** (11 endpoints): stats, capture, list/view snapshots, URL tracking, schedule management, search, scheduler control

**Addressbook** (3 endpoints): list/add/remove subscriptions

## Design Philosophy

- **Dark mode by default**: `oklch(0.141 0.005 285.823)` background with light text
- **shadcn/ui patterns**: consistent component design with `cn()` utility and `cva` variants
- **Microservices**: each backend service is independent with its own SQLite database (wayback + crawler share a volume)
- **Docker-only workflow**: no manual dependency installation; `docker compose up` is the only command needed

## Security

- API key authentication on all endpoints
- i2pd I2PControl uses HTTPS with custom SHA256 certificate
- nginx reverse proxy handles all external traffic
- i2pd HTTP proxy accessible only on the Docker network (ports mapped for host access)

## Performance

- Asynchronous Python (FastAPI + httpx + aiosqlite) for non-blocking I/O
- WAL mode for shared SQLite access between crawler and wayback
- Parallel crawl workers share a single HTTPX client connection pool
- Vite HMR for frontend development
- Frontend static build served by nginx in production
