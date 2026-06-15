# Prism — Session Context

You are working on **Prism**, a Docker-based web dashboard for monitoring, browsing, and managing an i2pd router. Codebase at `/Users/elias/Developer/prism`.

## Stack
- **Frontend**: React 19 + TypeScript + Vite 6 + Tailwind CSS 4 (shadcn/ui, wouter routing)
- **Backend**: 6 Python 3.11 FastAPI microservices
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

## CapsCard (Bandwidth Capabilities)
- Component at `frontend/client/src/components/CapsCard.tsx`
- Parses the raw caps string (e.g. `PU`, `FfRX`) to detect the current I2P bandwidth level flag (K/L/M/N/O/P/X)
- Shows a 7-position step slider mapped to I2P bandwidth classes:
  - K=12, L=32, M=64, N=128, O=256, P=2048, X=unlimited
- Each flag label has a tooltip explaining its bandwidth range
- Also displays reachability status (R=reachable, U=unreachable/firewalled) from the caps string
- Uses existing `POST /api/bandwidth/set` endpoint — no backend changes needed
- Replaced the old dual In/Out KB/s number inputs in `Home.tsx`
- Auto bandwidth toggle retained (connection-aware via `navigator.connection`)

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

## Known Issues
- **i2pd v2.60.0 LeaseSet publishing**: "Publish confirmation was not received" repeats indefinitely despite tunnels being built and SAM sessions OK — floodfill nodes don't respond. Same issue with both server tunnels and SAM sessions.
- **I2PControl spam**: "RouterInfo unknown request Token" 3x/sec from prism-router polling

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
