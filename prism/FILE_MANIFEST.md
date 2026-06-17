# Prism — File Manifest

## Backend (3 microservices + SAM Tunnel)

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

### Addressbook (`backend/services/addressbook/`)
```
addressbook/
├── Dockerfile
└── main.py              # Subscription management, hosts.txt parsing (CSV + =separated)
```

### SAM Tunnel Service (`prism/i2pd/abyssal-tunnel/`)
```
abyssal-tunnel/
├── Dockerfile
└── tunnel.py            # SAM streaming server: creates sessions, handles STREAM ACCEPT, proxies to backends
```

> **Note:** Crawler and Wayback services (and public addressbook) live in `../abyssal/abyssal/` (monorepo).

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
    ├── App.tsx                     # wouter routes (/dashboard, /browser, /addressbook)
    ├── index.css                   # Tailwind CSS + dark theme
    ├── lib/utils.ts                # cn() utility
    ├── hooks/
    │   └── useI2pdApi.ts           # All API calls + polling hooks
    ├── pages/
    │   ├── Home.tsx                # Dashboard: health gauge, status, bandwidth, tunnels
    │   ├── BrowserPage.tsx         # Tabbed I2P browser with bookmarks
    │   └── AddressbookPage.tsx     # Subscription management
    └── components/
        ├── RouterHealthCard.tsx    # Circular health gauge with auto-scaling bandwidth
        ├── EepsiteCard.tsx         # Abyssal SAM tunnel eepsite b32 addresses display
        └── ui/                     # shadcn/ui primitives (button, card, dialog, input, badge, etc.)
```

### Abyssal Frontend (`../abyssal/frontend/client/src/`)

```
├── App.tsx                  # wouter routes (/, /browse, /site/:hostname, /wayback, /addressbook, /admin)
├── hooks/
│   └── useAbyssalApi.ts     # All Abyssal API calls + types (search, crawl, wayback, addressbook)
└── pages/
    ├── SearchPage.tsx        # FTS5 full-text search with facets + bookmarks
    ├── DirectoryPage.tsx     # Site directory with filter/sort
    ├── SitePage.tsx          # Site detail: unified hostname+b32, address helper, hosts.txt copy
    ├── WaybackPage.tsx       # Wayback snapshot viewer with capture
    ├── AddressBookPage.tsx   # Public addressbook with live search, hosts.txt export
    └── AdminPage.tsx         # Crawl admin: start jobs, toggle completed, pause/resume/rerun/delete
```

## Configuration (Prism)

```
├── docker-compose.yml             # Production compose (4 services: router, browser, addressbook, frontend)
├── docker-compose.override.yml    # Dev override (volume mounts + hot-reload)
├── .env                           # Environment variables
├── nginx/
│   └── default.conf               # Reverse proxy config with resolver
└── i2pd/
    ├── i2pd.conf                   # i2pd configuration (HTTP proxy, I2PControl, SAM)
    ├── tunnels.conf                # (empty — server tunnels moved to SAM)
    ├── abyssal-tunnel/             # SAM tunnel service
    │   ├── Dockerfile
    │   └── tunnel.py
    └── certs/
        ├── i2pcontrol.crt.pem      # SHA256 certificate for I2PControl
        └── i2pcontrol.key.pem      # Private key
```

> **Note:** Full monorepo config (nginx, all services) is in `../abyssal/docker-compose.yml`.

## Documentation

```
├── AGENTS.md              # Agent guide + pre-commit checklist (Prism + Abyssal)
├── SESSION_PROMPT.md      # Session context, SAM tunnel docs, known issues
├── PROJECT_SUMMARY.md     # Architecture overview
├── FILE_MANIFEST.md       # This file
├── README.md              # Main documentation
├── QUICKSTART.md          # One-command quick start
└── DEPLOYMENT.md          # Production deployment

> **Root repo (../AGENTS.md)** has the full pre-commit checklist covering all 8 containers.
```

## File Statistics

### Backend (~1,500 lines)
- router/main.py: ~280 lines
- browser/main.py: ~160 lines
- addressbook/main.py: ~210 lines
- router/common/config.py: ~25 lines
- i2pd/abyssal-tunnel/tunnel.py: ~300 lines

### Frontend (~2,000 lines)
- App.tsx: ~60 lines
- Home.tsx: ~400 lines
- BrowserPage.tsx: ~750 lines
- AddressbookPage.tsx: ~150 lines
- RouterHealthCard.tsx: ~150 lines
- EepsiteCard.tsx: ~55 lines
- useI2pdApi.ts: ~750 lines

### Docker/Config (~250 lines)
- docker-compose.yml: ~100 lines
- docker-compose.override.yml: ~60 lines
- nginx/default.conf: ~60 lines
- i2pd/i2pd.conf: ~50 lines

### Documentation (~800 lines)
- AGENTS.md: ~100 lines
- PROJECT_SUMMARY.md: ~150 lines
- FILE_MANIFEST.md: ~120 lines
- SESSION_PROMPT.md: ~60 lines
- README.md: ~310 lines
- QUICKSTART.md: ~60 lines
- DEPLOYMENT.md: ~150 lines

### Total: ~4,500 lines

### Abyssal Backend (`../abyssal/abyssal/`, ~1,700 lines)
- api/router.py: ~300 lines (search, crawler, wayback, page viewer, eepsite, addressbook endpoints)
- crawler/worker.py: ~246 lines, db.py: ~427 lines, scheduler.py: ~105 lines, fetcher.py: ~200 lines
- wayback/storage.py: ~101 lines, db.py: ~234 lines, rewrite.py: ~144 lines
- db/search.py: ~213 lines
- resolver/resolver.py: ~90 lines
- classifier/classify.py: ~300 lines
- seeds.py: ~17 lines, config.py: ~7 lines
- backend/main.py: ~91 lines

### Abyssal Frontend (`../abyssal/frontend/client/src/`, ~1,100 lines)
- App.tsx: ~37 lines, useAbyssalApi.ts: ~128 lines
- SearchPage.tsx: ~199 lines, DirectoryPage.tsx: ~150 lines
- SitePage.tsx: ~192 lines, WaybackPage.tsx: ~122 lines
- AddressBookPage.tsx: ~260 lines, AdminPage.tsx: ~216 lines

### Total (full monorepo): ~7,300 lines
