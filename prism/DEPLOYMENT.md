# Deployment Guide

## Production Mode

```bash
docker compose -f docker-compose.yml up --build -d
```

This starts all services without the dev override — no hot-reload, no volume mounts for source code. The frontend is served as a static build by nginx on port 80.

## Architecture

```
External ──► nginx:80 ──┬─► api-router:8001
                        ├─► api-browser:8002
                        ├─► api-crawler:8003
                        ├─► api-wayback:8004
                        ├─► api-addressbook:8005
                        └─► frontend:80
```

i2pd ports (4444, 4445, 7070, 7650) are mapped to the host for direct access.

## Persistent Volumes

### wayback-data
Contains:
- `crawler.db` — crawler jobs, pages, site status
- `archive/` — Wayback snapshot HTML files (organized by hostname)

Backup:
```bash
docker run --rm -v wayback-data:/data -v $(pwd):/backup alpine tar czf /backup/wayback-backup-$(date +%Y%m%d).tar.gz -C /data .
```

Restore:
```bash
docker run --rm -v wayback-data:/data -v $(pwd):/backup alpine tar xzf /backup/wayback-backup-20260613.tar.gz -C /data
```

### i2pd-data
Contains i2pd router keys, certificates, and config. The local `./i2pd/i2pd.conf` is bind-mounted on top of it.

## Environment Variables

All set in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `API_KEY` | `dev-key-12345` | Auth key for all API endpoints |
| `I2PD_HTTP_PROXY` | `http://i2pd:4444` | i2pd HTTP proxy address |
| `I2PD_API_URL` | `https://i2pd:7650` | I2PControl HTTPS endpoint |
| `I2PD_PASSWORD` | `itoopie` | I2PControl password |
| `WEBCONSOLE_URL` | `http://i2pd:7070` | i2pd webconsole |
| `DB_PATH` | `/data/crawler.db` | Shared SQLite database path |
| `ARCHIVE_ROOT` | `/data/archive` | Wayback snapshot storage |
| `I2PD_CONF_PATH` | `/i2pd-data/i2pd.conf` | i2pd config (addressbook writes here) |
| `I2PD_DATA_PATH` | `/i2pd-data` | i2pd data directory |

## Port Mapping

| Port | Service | Purpose |
|------|---------|---------|
| 80 | nginx | Web dashboard |
| 4444 | i2pd | HTTP proxy |
| 4445 | i2pd | HTTP proxy (.eep) |
| 7070 | i2pd | Webconsole |
| 7650 | i2pd | I2PControl (HTTPS) |

## Monitoring

```bash
# All services
docker compose ps

# Individual logs
docker compose logs -f api-crawler
docker compose logs -f i2pd

# Resource usage
docker stats
```

## Updating

```bash
git pull
docker compose up --build -d
```

The `wayback-data` and `i2pd-data` volumes persist across rebuilds.

## Troubleshooting

### i2pd won't start
Check i2pd logs: `docker compose logs i2pd`. First boot can take 1-3 minutes to generate router keys.

### API returns 403
Verify `API_KEY` in `.env` matches the `x-api-key` header sent by the frontend. The frontend reads `VITE_API_KEY` from its environment.

### Wayback snapshots empty
The CSS inliner fetches external stylesheets through the I2P proxy. If the target site is slow or the proxy hasn't built tunnels, CSS may not be inlined. The raw HTML is always stored.

### Disk space
Wayback snapshots accumulate in the `wayback-data` volume. Each snapshot is a small HTML file (typically 5-50KB). Monitor with `docker system df`.
