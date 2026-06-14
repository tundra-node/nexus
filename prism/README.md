# Prism — I2P Dashboard

A full-stack web dashboard for monitoring and controlling an i2pd router, featuring a built-in I2P browser, web crawler, Wayback Machine archive, and addressbook manager — all containerized via Docker Compose.

## Quick Start

```bash
docker compose up --build
```

Open http://localhost — everything runs behind an nginx reverse proxy.

## Features

### Dashboard
- **Router Health Card**: Circular gauge (0-100) with status badges, peer/tunnel/routers/success-rate metrics, auto-scaling bandwidth (B/s, KB/s, MB/s, GB/s)
- **Status**: Real-time uptime, active peers, tunnel counts
- **Bandwidth**: Live inbound/outbound with animated bars
- **Tunnel Manager**: List tunnels with state/direction indicators and toggle controls

### I2P Browser
- Proxy `.i2p` sites through the i2pd HTTP proxy
- Link rewriting so all internal links go through the proxy
- Bookmarks manager (persisted to disk)
- Tabbed browsing with back/forward navigation

### Web Crawler
- **Parallel crawling**: Configurable concurrency (1-20 workers) — all workers share the same I2P proxy connection
- **Speed control**: Adjustable delay (0-60s) between requests per worker
- **Unlimited mode**: Set max_pages ≤ 0 for unbounded crawling
- **Pause/Resume**: Stop and restart a job without losing progress
- **b32/AH resolution**: Automatically resolves `.i2p` hostnames to base32 addresses and address helpers via I2P jump services (stats.i2p, notbob.i2p, reg.i2p). Failed lookups are retried on subsequent encounters
- **Site classification**: Auto-detects language (14 languages via stopword + script detection) and site type (forum, wiki, blog, market, etc.)
- **Delete confirmation**: Confirms before removing jobs (Wayback snapshots are preserved)
- **Wayback integration**: Every crawled page is automatically archived as a Wayback snapshot

### Wayback Machine
- Capture and browse historical snapshots of `.i2p` sites
- CSS inlining at capture time (external CSS downloaded and embedded)
- View-time URL rewriting (images, scripts, fonts proxied live)
- Configurable re-capture scheduler per URL
- Search snapshots by URL or title
- Calendar + list view modes

### Addressbook
- Subscribe to remote hosts.txt files (reg.i2p, etc.)
- Parser handles both CSV and `=`-separated formats
- Auto-writes subscriptions to i2pd config

### Router Health
- `GET /api/router-health` returns a 0-100 health score computed from network status, peer count, tunnel success rate, and bandwidth
- Endpoint polls i2pd's internal stats and I2PControl JSON-RPC

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      nginx (port 80)                     │
│  routes /api/router/* → api-router:8001                  │
│  routes /api/browser/* → api-browser:8002                │
│  routes /api/crawler/* → api-crawler:8003                │
│  routes /api/wayback/* → api-wayback:8004                │
│  routes /api/addressbook/* → api-addressbook:8005        │
│  routes /* → frontend:80                                 │
└──────┬──────────────────────────────────────────────────┘
       │
┌──────▼──────────────────────────────────────────────────┐
│  i2pd (purplei2p/i2pd)                                   │
│  HTTP Proxy :4444  │  I2PControl :7650  │  Webconsole    │
└─────────────────────────────────────────────────────────┘
```

### Services

| Service | Port | Description |
|---------|------|-------------|
| `api-router` | 8001 | Router dashboard — proxies i2pd JSON-RPC |
| `api-browser` | 8002 | I2P browser proxy + bookmarks |
| `api-crawler` | 8003 | Crawl job management + background workers |
| `api-wayback` | 8004 | Wayback Machine capture + replay |
| `api-addressbook` | 8005 | Addressbook subscriptions |
| `frontend` | 80 | React 19 + Vite + Tailwind CSS |
| `nginx` | 80 | Reverse proxy (exposed) |
| `i2pd` | — | I2P router (exposes 4444, 4445, 7650, 7070) |

### Volumes

| Volume | Purpose |
|--------|---------|
| `wayback-data` | Crawler DB + archive snapshots |
| `i2pd-data` | i2pd config + certificates + router keys |

## API Endpoints

All endpoints require `x-api-key` header (dev key: `dev-key-12345`). Some also accept `api_key` query parameter for link/share support.

### Router Dashboard (`/api/router*`)

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/api/router-health` | Health score (0-100), uptime, peers, tunnels, bandwidth, network status |
| GET | `/api/status` | Router status (uptime, peers, tunnels) |
| GET | `/api/bandwidth` | Bandwidth rates (in/out) |
| GET | `/api/tunnels` | Active tunnel list |
| GET | `/api/router-info` | Router version, identity, network ID |
| GET | `/api/router-details` | Detailed router info (caps, floodfills, etc.) |
| GET | `/api/commands` | Available i2pd commands |
| POST | `/api/command/{id}` | Execute a command |
| GET | `/api/transports` | Transport peers |
| GET | `/api/local-destinations` | Local I2P tunnels |

### Browser Proxy (`/api/browser*`)

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/api/browser/proxy?url=` | Fetch & rewrite a `.i2p` page |
| GET | `/api/browser/bookmarks` | List bookmarks |
| POST | `/api/browser/bookmarks` | Save bookmarks |

### Crawler (`/api/crawler*`)

| Method | Route | Description |
|--------|-------|-------------|
| POST | `/api/crawler/start` | Start a crawl job (`url`, `max_pages`, `max_depth`, `concurrency`, `delay_seconds`) |
| GET | `/api/crawler/jobs` | List all jobs |
| GET | `/api/crawler/jobs/{id}` | Get job details |
| DELETE | `/api/crawler/jobs/{id}` | Delete job |
| POST | `/api/crawler/jobs/{id}/rerun` | Rerun a job |
| POST | `/api/crawler/jobs/{id}/pause` | Pause a running job |
| POST | `/api/crawler/jobs/{id}/resume` | Resume a paused job |
| GET | `/api/crawler/pages` | Search pages (`q`, `job_id`, `search_content`, `limit`, `offset`) |
| GET | `/api/crawler/pages/{id}` | Get page metadata + content |
| GET | `/api/crawler/pages/{id}/view` | View page HTML (URL rewriting applied) |
| GET | `/api/crawler/site-status` | Online/offline status per hostname |

### Wayback Machine (`/api/wayback*`)

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/api/wayback/stats` | Overall stats (snapshots, URLs, size) |
| POST | `/api/wayback/capture` | Capture a snapshot now |
| GET | `/api/wayback/snapshots?url=` | List snapshots for a URL |
| GET | `/api/wayback/snapshots/{id}` | Get snapshot metadata + content |
| GET | `/api/wayback/snapshots/{id}/view` | View snapshot HTML (URL rewriting applied) |
| GET | `/api/wayback/urls` | List all tracked URLs |
| GET | `/api/wayback/urls/{url}` | Get URL info + recent snapshots |
| POST | `/api/wayback/urls/{url}/schedule` | Set re-capture schedule |
| DELETE | `/api/wayback/urls/{url}/schedule` | Clear schedule |
| GET | `/api/wayback/search?q=` | Search snapshots |
| GET/POST | `/api/wayback/scheduler` | Control the re-capture scheduler |

### Addressbook (`/api/addressbook*`)

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/api/addressbook/subscriptions` | List subscriptions |
| POST | `/api/addressbook/subscriptions` | Add subscription (`url`) |
| DELETE | `/api/addressbook/subscriptions?url=` | Remove subscription |

## Configuration (`.env`)

```ini
# Authentication
API_KEY=dev-key-12345

# I2P services (Docker network)
I2PD_HTTP_PROXY=http://i2pd:4444
I2PD_API_URL=https://i2pd:7650
I2PD_PASSWORD=itoopie
WEBCONSOLE_URL=http://i2pd:7070

# Data paths
DB_PATH=/data/crawler.db
ARCHIVE_ROOT=/data/archive

# i2pd config path (for addressbook service)
I2PD_CONF_PATH=/i2pd-data/i2pd.conf
I2PD_DATA_PATH=/i2pd-data
```

## Development

```bash
# Start with hot-reload (dev override mounts source directories)
docker compose up --build

# Rebuild a single service
docker compose up --build -d api-crawler

# View logs
docker compose logs -f api-crawler

# Run backend tests
cd backend && python3 test_api.py
```

The dev override (`docker-compose.override.yml`) mounts source directories into each container and enables `uvicorn --reload` for instant code reload. The frontend uses Vite dev server (port 5173) with HMR.

## Project Structure

```
prism/
├── backend/
│   ├── requirements.txt              # Shared Python dependencies
│   └── services/
│       ├── router/                   # Router dashboard service
│       ├── browser/                  # I2P browser proxy service
│       ├── crawler/                  # Web crawler service
│       │   ├── main.py
│       │   └── crawler/
│       │       ├── router.py         # API endpoints
│       │       ├── worker.py         # Background crawl workers
│       │       ├── db.py             # SQLite database layer
│       │       ├── classify.py       # Language + site type detection
│       │       ├── resolver.py       # b32/AH resolution via jump services
│       │       └── scheduler.py      # Auto-recrawl scheduler
│       ├── wayback/                  # Wayback Machine service
│       │   ├── main.py
│       │   └── wayback/
│       │       ├── router.py         # API endpoints
│       │       ├── db.py             # SQLite database layer
│       │       ├── storage.py        # Snapshot file storage
│       │       ├── rewrite.py        # CSS inlining + URL rewriting
│       │       └── scheduler.py      # Re-capture scheduler
│       ├── addressbook/              # Addressbook service
│       └── router/common/            # Shared config module
├── frontend/
│   └── client/                       # React 19 + Vite + Tailwind CSS
│       └── src/
│           ├── pages/                # Home, BrowserPage, CrawlerPage,
│           │                         # WaybackPage, AddressbookPage
│           ├── components/           # RouterHealthCard + shadcn/ui
│           └── hooks/                # useI2pdApi.ts (all API calls)
├── i2pd/                             # i2pd configuration + certs
├── nginx/                            # nginx reverse proxy config
├── docker-compose.yml
├── docker-compose.override.yml       # Dev hot-reload configuration
├── .env
└── AGENTS.md                         # Agent guide
```

## Troubleshooting

### Blank page in snapshot viewer
The Wayback Machine and Crawler page viewers use a backend view endpoint that rewrites resource URLs through the I2P browser proxy. If the proxy is down or i2pd hasn't established tunnels yet, images/styles may not load. Sandbox is `allow-same-origin allow-scripts` — if a site requires additional permissions, the snapshot will render as raw HTML source.

### i2pd not connecting
The i2pd container may take 1-3 minutes to bootstrap and establish peer connections. Check with `docker compose logs -f i2pd`. The webconsole can be accessed at http://localhost:7070 (requires `Host: localhost` header).

### API key errors
All API calls require `x-api-key` header matching `API_KEY` in `.env`. The browser proxy and snapshot view endpoints also accept `api_key` query parameter. Default dev key is `dev-key-12345`.

### Port conflicts
If ports 80, 4444, 4445, 7070, or 7650 are in use, modify the port mappings in `docker-compose.yml`.

## License

MIT
