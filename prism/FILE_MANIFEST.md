# Prism — File Manifest

## Backend (6 microservices)

### Router Dashboard (`backend/services/router/`)
```
router/
├── Dockerfile
├── main.py              # FastAPI app, 14 endpoints proxying i2pd JSON-RPC + I2PControl + webconsole
└── common/config.py     # Shared config module (read by all services)
```

### I2P Browser (`backend/services/browser/`)
```
browser/
├── Dockerfile
└── main.py              # Proxy endpoint + bookmarks CRUD
```

### Web Crawler (`backend/services/crawler/`)
```
crawler/
├── Dockerfile
├── main.py              # FastAPI app (starts scheduler on boot)
└── crawler/
    ├── __init__.py
    ├── router.py         # 11 REST endpoints (start, list, delete, pause, resume, rerun, search, view, site-status)
    ├── worker.py         # Background crawl workers (parallel, configurable delay, b32 resolution)
    ├── db.py             # SQLite access (jobs, pages, queue, site_status)
    ├── classify.py       # Multi-layer language detection (14 langs) + site type classification
    ├── resolver.py       # b32/AH resolution via I2P jump services
    └── scheduler.py      # Auto-recrawl loop (24h)
```

### Wayback Machine (`backend/services/wayback/`)
```
wayback/
├── Dockerfile
├── main.py              # FastAPI app
└── wayback/
    ├── __init__.py
    ├── router.py         # 11 REST endpoints (stats, capture, list/view snapshots, URL tracking, scheduling)
    ├── db.py             # SQLite access (snapshots, tracked URLs, schedule log)
    ├── storage.py        # Snapshot file I/O (store/load/delete)
    ├── rewrite.py        # CSS inliner + view-time URL rewriting
    └── scheduler.py      # Re-capture scheduler
```

### Addressbook (`backend/services/addressbook/`)
```
addressbook/
├── Dockerfile
└── main.py              # Subscription management, hosts.txt parsing (CSV + =separated)
```

## Frontend

```
frontend/client/
├── Dockerfile
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json
└── src/
    ├── main.tsx
    ├── App.tsx                     # wouter routes (/, /browser, /crawler, /wayback, /addressbook)
    ├── index.css                   # Tailwind CSS + dark theme
    ├── lib/utils.ts                # cn() utility
    ├── hooks/
    │   └── useI2pdApi.ts           # All API calls (40+ functions) + polling hooks
    ├── pages/
    │   ├── Home.tsx                # Dashboard: health gauge, status, bandwidth, tunnels
    │   ├── BrowserPage.tsx         # Tabbed I2P browser with bookmarks
    │   ├── CrawlerPage.tsx         # Crawler UI: job cards, page list, preview, delete confirmation
    │   ├── WaybackPage.tsx         # Wayback: capture, snapshot list, calendar, viewer
    │   └── AddressbookPage.tsx     # Subscription management
    └── components/
        ├── RouterHealthCard.tsx    # Circular health gauge with auto-scaling bandwidth
        └── ui/                     # shadcn/ui primitives (button, card, dialog, input, badge, etc.)
```

## Configuration

```
├── docker-compose.yml             # Production compose (8 services)
├── docker-compose.override.yml    # Dev override (volume mounts + hot-reload)
├── .env                           # Environment variables
├── nginx/
│   └── default.conf               # Reverse proxy config with resolver
└── i2pd/
    ├── i2pd.conf                   # i2pd configuration (HTTP proxy, I2PControl, addressbook)
    └── certs/
        ├── i2pcontrol.crt.pem      # SHA256 certificate for I2PControl
        └── i2pcontrol.key.pem      # Private key
```

## Documentation

```
├── AGENTS.md              # Agent guide (for AI coding assistants)
├── README.md              # Main documentation
├── QUICKSTART.md          # One-command quick start
├── DEPLOYMENT.md          # Production deployment
├── PROJECT_SUMMARY.md     # Architecture overview
├── FILE_MANIFEST.md       # This file
└── SESSION_PROMPT.md      # Session context (for AI assistants)
```

## File Statistics

### Backend (~3,200 lines)
- router/main.py: ~280 lines
- browser/main.py: ~160 lines
- crawler/main.py: ~45 lines
- crawler/router.py: ~210 lines
- crawler/worker.py: ~200 lines
- crawler/db.py: ~400 lines
- crawler/classify.py: ~280 lines
- crawler/resolver.py: ~110 lines
- crawler/scheduler.py: ~65 lines
- wayback/router.py: ~305 lines
- wayback/db.py: ~400 lines
- wayback/storage.py: ~125 lines
- wayback/rewrite.py: ~195 lines
- wayback/scheduler.py: ~175 lines
- addressbook/main.py: ~200 lines
- router/common/config.py: ~25 lines

### Frontend (~2,500 lines)
- App.tsx: ~60 lines
- Home.tsx: ~250 lines
- BrowserPage.tsx: ~750 lines
- CrawlerPage.tsx: ~550 lines
- WaybackPage.tsx: ~900 lines
- AddressbookPage.tsx: ~150 lines
- RouterHealthCard.tsx: ~150 lines
- useI2pdApi.ts: ~685 lines

### Docker/Config (~300 lines)
- docker-compose.yml: ~120 lines
- docker-compose.override.yml: ~70 lines
- nginx/default.conf: ~60 lines
- i2pd/i2pd.conf: ~50 lines

### Documentation (~1,000 lines)
- README.md: ~310 lines
- PROJECT_SUMMARY.md: ~230 lines
- QUICKSTART.md: ~60 lines
- DEPLOYMENT.md: ~150 lines
- FILE_MANIFEST.md: ~150 lines
- AGENTS.md: ~60 lines
- SESSION_PROMPT.md: ~40 lines

### Total: ~7,000 lines
