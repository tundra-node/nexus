# Nexus — I2P Search Engine + Dashboard

Monorepo for two connected I2P tools:

- **Abyssal** — Public I2P search engine + Wayback Machine + crawler (`./abyssal/`)
- **Prism** — Private i2pd router dashboard, browser, addressbook (`./prism/`)

## Quick Start

```bash
docker compose -f abyssal/docker-compose.yml up --build
```

- `http://localhost` — Abyssal search engine (public)
- `http://localhost/dashboard/` — Prism dashboard (private)

## Architecture

| Service | What it does | Type |
|---------|-------------|------|
| **Abyssal** | Search, crawl, Wayback archive | Public |
| **Prism** | Router dashboard, I2P browser, addressbook | Private (api-key) |
| **i2pd** | I2P router (HTTP proxy, I2PControl) | Infrastructure |

Both share the same i2pd instance and nginx reverse proxy. Prism APIs require the `api-key` header; Abyssal's search/directory/Wayback browsing are public.

## API Key

Default: `dev-key-12345`. Set `API_KEY` in `abyssal/.env`.
