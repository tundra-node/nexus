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

## Dev Commands
```sh
# Rebuild single service
docker compose up --build -d api-router

# View logs
docker compose logs -f api-router

# Run backend tests
cd backend && python3 test_api.py
```
