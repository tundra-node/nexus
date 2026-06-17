# Prism — Project Summary

## Overview

Prism is a containerized web dashboard for monitoring and browsing I2P sites via an i2pd router. It runs **8 Docker services** (3 Python microservices + React frontend + SAM tunnel + nginx + i2pd) behind an nginx reverse proxy, with an i2pd router in a separate container.

**Crawler and Wayback Machine functionality have moved to the Abyssal service** in the monorepo (see `../abyssal/`).

## Technology Stack

### Backend (3 microservices)

| Service | Framework | Port | Purpose |
|---------|-----------|------|---------|
| api-router | FastAPI + httpx | 8001 | Proxies i2pd JSON-RPC + I2PControl + webconsole |
| api-browser | FastAPI + httpx + BeautifulSoup | 8002 | I2P HTTP proxy with link rewriting |
| api-addressbook | FastAPI + aiosqlite + httpx | 8005 | Addressbook subscription management |

### Frontend

| Component | Technology | Version |
|-----------|------------|---------|
| Framework | React | 19 |
| Styling | Tailwind CSS | 4 |
| Build | Vite | 8 |
| Routing | Wouter | 3 |
| UI Components | shadcn/ui | Latest |
| Icons | Lucide React | 1.0 |
| Notifications | Sonner | 2 |

### Infrastructure

| Component | Technology |
|-----------|------------|
| Reverse Proxy | nginx (with resolver 127.0.0.11 for Docker DNS) |
| I2P Router | purplei2p/i2pd:latest |
| SAM Tunnel Service | Python 3.11 (custom) |
| Orchestration | Docker Compose (project: nexus) |
| Volumes | abyssal-data, i2pd-data |
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

### 4. Router Health Endpoint
- `GET /api/router-health` returns a composite health score (0-100)
- Computed from: network status, peer count, tunnel success rate, bandwidth activity
- Returns detailed breakdown: uptime, peers, tunnels, bandwidth, network status, floodfill/reachable flags

### 5. SAM Tunnel Service (for Abyssal Eepsites)
- Python 3.11 service connecting to i2pd SAM on port 7656
- Generates persistent keys via `DEST GENERATE` (requires `HELLO VERSION` handshake)
- Creates STREAM sessions for abyssal-frontend (port 80) and abyssal-backend (port 8000)
- Unique session IDs (`tun_{name}_{timestamp}_{random}`) avoid `DUPLICATED_ID`
- Computes b32 addresses: `base64_decode(dest) → SHA-256 → base32_encode → .b32.i2p`
- Key files persist at `/data/tunnel-keys/` (Docker volume `abyssal-data`)

## API Architecture

### Authentication
All endpoints require `x-api-key` header. Some also accept `api_key` query parameter:
- Browser proxy: `GET /api/browser/proxy?url=&api_key=`
- Browser proxy rewritten URLs: `api_key` embedded in URL

### Endpoint Summary

**Router Dashboard** (8 endpoints): health, status, bandwidth, tunnels, router-info, router-details, transports, local-destinations, commands

**Browser** (3 endpoints): proxy fetch, bookmarks CRUD

**Addressbook** (3 endpoints): list/add/remove subscriptions

> **Note:** Crawler (11 endpoints), Wayback (11 endpoints), and Public Addressbook have moved to the Abyssal service in the monorepo (`../abyssal/`). The public addressbook at `GET /api/abyssal/addressbook` is intentionally unauthenticated.

## Design Philosophy

- **Dark mode by default**: `oklch(0.141 0.005 285.823)` background with light text
- **shadcn/ui patterns**: consistent component design with `cn()` utility and `cva` variants
- **Microservices**: each backend service is independent with its own SQLite database
- **Docker-only workflow**: no manual dependency installation; `docker compose up` is the only command needed
- **Monorepo**: Prism (dashboard) + Abyssal (search/crawler/wayback) share nginx + i2pd

## Security

- API key authentication on all endpoints
- i2pd I2PControl uses HTTPS with custom SHA256 certificate
- nginx reverse proxy handles all external traffic
- i2pd HTTP proxy accessible only on the Docker network (ports mapped for host access)
- I2PControl `Token` param required in all JSON-RPC calls after `Authenticate` (i2pd v2.60.0)

## Performance

- Asynchronous Python (FastAPI + httpx + aiosqlite) for non-blocking I/O
- WAL mode for shared SQLite access
- Vite 8 HMR for frontend development
- Frontend static build served by nginx in production
