# Quick Start

Get Prism running in one command.

## Prerequisites

- Docker & Docker Compose

## 1. Clone & Start

```bash
git clone <repo> prism
cd prism
docker compose up --build
```

That's it. Open **http://localhost** in your browser.

## What You Get

| URL | What |
|-----|------|
| http://localhost | Prism dashboard |
| http://localhost:5173 | Frontend dev server (HMR) |
| http://localhost:4444 | i2pd HTTP proxy |
| http://localhost:7070 | i2pd webconsole (set `Host: localhost` header) |

## Default API Key

Dev key is `dev-key-12345`. Set a different one in `.env`:

```ini
API_KEY=your-secure-key
```

## Try It

**Browse a site:**
1. Click **Browser** in the sidebar
2. Type `stats.i2p` and hit Enter

**Crawl a site:**
1. Click **Crawler** in the sidebar
2. Enter a URL, set Parallel=3, Delay=0.5s
3. Click Start — pages appear in real-time

**Archive a page:**
1. Click **Wayback** in the sidebar
2. Enter a URL and click Save Page
3. Click the snapshot to view it

**Check router health:**
- The Home page shows a health gauge with bandwidth, peers, and tunnel metrics

## Configuration (`.env`)

```ini
API_KEY=dev-key-12345
I2PD_HTTP_PROXY=http://i2pd:4444
I2PD_API_URL=https://i2pd:7650
I2PD_PASSWORD=itoopie
WEBCONSOLE_URL=http://i2pd:7070
DB_PATH=/data/crawler.db
ARCHIVE_ROOT=/data/archive
I2PD_CONF_PATH=/i2pd-data/i2pd.conf
I2PD_DATA_PATH=/i2pd-data
```

## Next Steps

- Read `README.md` for full documentation
- Check `AGENTS.md` for agent-specific notes
- Run `docker compose logs -f api-crawler` to watch crawlers in action
