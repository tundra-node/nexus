# Prism — Session Context

You are working on **Prism**, a Docker-based web dashboard for monitoring, browsing, and managing an i2pd router. Codebase at `C:\Users\Zeine\Developer\nexus\prism` (monorepo: `nexus/`).

## Stack
- **Frontend**: React 19 + TypeScript + Vite 8 + Tailwind CSS 4 (shadcn/ui, wouter routing)
- **Backend**: 3 Python 3.11 FastAPI microservices (router, browser, addressbook — crawler/wayback moved to Abyssal)
- **Infrastructure**: Docker Compose, nginx reverse proxy, purplei2p/i2pd container

## Quick Start
```sh
docker compose up --build
```
Frontend: http://localhost, Dev server: http://localhost:5173

## API Convention
All `/api/*` routes require `x-api-key` header. Dev key: `"dev-key-12345"`. Some endpoints also accept `api_key` query param (browser proxy, view endpoints).

## Key Architecture
- **api-router** (8001): Proxies i2pd JSON-RPC + webconsole scraping
- **api-browser** (8002): Proxy `.i2p` through i2pd HTTP proxy, rewrites links
- **api-addressbook** (8005): Addressbook subscription management
- **nginx** (80): Routes `/api/<service>/*` to correct backend, lazy DNS for frontend
- **i2pd**: HTTP proxy 4444, I2PControl 7650, webconsole 7070

> Crawler + Wayback functionality has moved to the **Abyssal** service in the monorepo. Prism is the private dashboard layer only.

## Conventions
- Dark mode default (Tailwind CSS v4)
- shadcn/ui patterns: `cn()` util, named exports from `@/components/ui/*`
- API calls in `useI2pdApi.ts`
- Polling hooks: `useI2pdRouterHealth()` (5s)

## Bandwidth Letter Presets
- Inline in `Home.tsx` (no separate component needed)
- Replaced old dual In/Out KB/s number inputs with letter preset buttons: K(16), L(32), M(64), N(128), O(256), P(512), X(1024)
- Auto mode maps connection type: slow-2g→K, 2g→L, 3g→N, 4g→P
- Uses `POST /api/bandwidth/set` endpoint with symmetric in/out KB/s values
- Current letter persisted to `localStorage("bwLetter")`

## Eepsite Card
- Component at `frontend/client/src/components/EepsiteCard.tsx`
- Displays Abyssal SAM tunnel b32 addresses on the dashboard (in the Router Info grid)
- Fetches from `GET /api/abyssal/eepsite` (public endpoint, no auth needed)
- Each tunnel shows name, collapsible b32 address, and host:port
- Auto-polls every 30s

## SAM Tunnel Service (`prism/i2pd/abyssal-tunnel/`)
- Python 3.11 service connecting to i2pd SAM on port 7656
- Generates persistent keys via `DEST GENERATE` (requires `HELLO VERSION` handshake first)
- Creates STREAM sessions for each backend (abyssal-frontend:80, abyssal-api:8000)
- Uses unique session IDs (`tun_{name}_{timestamp}_{random}`) to avoid DUPLICATED_ID
- `DESTINATION=<priv>` (from PRIV=, NOT pub+priv) is the correct SAM session format
- Listens for STREAM STATUS notifications, spawns handler threads for incoming streams
- Handlers open SAM STREAM ACCEPT, then bidirectionally proxy between SAM and backends
- b32 computation: `base64_decode(destination) → SHA-256 → base32_encode → .b32.i2p`
- Key files persist at `/data/tunnel-keys/` (Docker volume `abyssal-data`)
- Writes `/data/tunnel-info.json` with name, b32, host, port for each tunnel (shared with abyssal-backend)
- Periodic info file rewrite every 30s in background thread

## Known Issues
- **i2pd v2.60.0 LeaseSet publishing**: "Publish confirmation was not received" warns repeat for HTTP/SOCKS client proxy destinations (outbound-only, expected behavior). SAM eepsite destinations use a separate code path and publish correctly via `SESSION CREATE`.
- **I2PControl Token**: `Token` param **required** in all JSON-RPC calls after `Authenticate` (i2pd v2.60.0). Fixed in `prism/backend/services/router/main.py`.

## Dev Commands
```sh
# Rebuild single service
docker compose up --build -d api-router

# Rebuild SAM tunnel
docker compose -f ../abyssal/docker-compose.yml build abyssal-tunnel

# View logs
docker compose logs -f api-router
docker compose -f ../abyssal/docker-compose.yml logs -f abyssal-tunnel

# Run backend tests
cd backend && python3 test_api.py
```
