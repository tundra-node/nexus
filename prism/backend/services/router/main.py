"""
Prism Router API — FastAPI route handlers.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware

from common.config import API_KEY
from .models import (
    StatusResponse,
    BandwidthResponse,
    TunnelEntry,
    TunnelsResponse,
    RouterInfoResponse,
    SetBandwidthRequest,
)

logger = logging.getLogger(__name__)

POLL_INTERVAL = 1

# ---------------------------------------------------------------------------
# App + CORS
# ---------------------------------------------------------------------------

app = FastAPI(title="Prism Router API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

async def verify_api_key(x_api_key: Optional[str]) -> None:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing API key")
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")

# ---------------------------------------------------------------------------
# Lazy-import client helpers to avoid circular imports
# ---------------------------------------------------------------------------

def _client():
    from . import client as _c
    return _c

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/api/status", response_model=StatusResponse)
async def get_status(api_key: Optional[str] = Header(None, alias="x-api-key")):
    await verify_api_key(api_key)
    try:
        data = await _client().i2p_router_info({
            "i2p.router.uptime": "",
            "i2p.router.netdb.activepeers": "",
            "i2p.router.net.tunnels.inbound": "",
            "i2p.router.net.tunnels.outbound": "",
            "i2p.router.status": "",
        })
        uptime = int(data.get("i2p.router.uptime", 0)) // 1000
        active_peers = int(data.get("i2p.router.netdb.activepeers", 0))
        tunnels_in = int(data.get("i2p.router.net.tunnels.inbound", 0))
        tunnels_out = int(data.get("i2p.router.net.tunnels.outbound", 0))
        return StatusResponse(
            uptime=uptime,
            active_peers=active_peers,
            tunnel_count=tunnels_in + tunnels_out,
            tunnels_in=tunnels_in,
            tunnels_out=tunnels_out,
            status="online" if active_peers > 0 else "connecting",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching status: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/bandwidth", response_model=BandwidthResponse)
async def get_bandwidth(api_key: Optional[str] = Header(None, alias="x-api-key")):
    await verify_api_key(api_key)
    c = _client()
    try:
        data = await c.i2p_router_info({
            "i2p.router.net.bw.inbound.1s": "",
            "i2p.router.net.bw.outbound.1s": "",
            "i2p.router.net.bw.inbound.15s": "",
            "i2p.router.net.bw.outbound.15s": "",
        })
        inbound_rate = float(data.get("i2p.router.net.bw.inbound.1s", 0))
        outbound_rate = float(data.get("i2p.router.net.bw.outbound.1s", 0))
        c.bandwidth_cache.total_inbound += int(inbound_rate)
        c.bandwidth_cache.total_outbound += int(outbound_rate)
        return BandwidthResponse(
            inbound_rate=inbound_rate,
            outbound_rate=outbound_rate,
            total_inbound=c.bandwidth_cache.total_inbound,
            total_outbound=c.bandwidth_cache.total_outbound,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching bandwidth: %s", e)
        return BandwidthResponse(
            inbound_rate=0, outbound_rate=0,
            total_inbound=c.bandwidth_cache.total_inbound,
            total_outbound=c.bandwidth_cache.total_outbound,
        )


@app.get("/api/tunnels", response_model=TunnelsResponse)
async def get_tunnels(api_key: Optional[str] = Header(None, alias="x-api-key")):
    await verify_api_key(api_key)
    c = _client()
    try:
        try:
            entries = await c.scrape_tunnels_page()
            if entries:
                return TunnelsResponse(tunnels=entries, total=len(entries))
        except Exception:
            pass
        data = await c.i2p_router_info({
            "i2p.router.net.tunnels.inbound": "",
            "i2p.router.net.tunnels.outbound": "",
        })
        tunnels_in = int(data.get("i2p.router.net.tunnels.inbound", 0))
        tunnels_out = int(data.get("i2p.router.net.tunnels.outbound", 0))
        tunnels = [
            TunnelEntry(id=f"inbound-{i}", state="established", direction="inbound")
            for i in range(tunnels_in)
        ] + [
            TunnelEntry(id=f"outbound-{i}", state="established", direction="outbound")
            for i in range(tunnels_out)
        ]
        return TunnelsResponse(tunnels=tunnels, total=len(tunnels))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching tunnels: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/router-info", response_model=RouterInfoResponse)
async def get_router_info(api_key: Optional[str] = Header(None, alias="x-api-key")):
    await verify_api_key(api_key)
    try:
        data = await _client().i2p_router_info({"i2p.router.version": "", "i2p.router.uptime": ""})
        return RouterInfoResponse(
            version=data.get("i2p.router.version", "unknown"),
            identity="unavailable via I2PControl",
            uptime=int(data.get("i2p.router.uptime", 0)) // 1000,
            net_id=2,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching router info: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/router-details")
async def get_router_details(api_key: Optional[str] = Header(None, alias="x-api-key")):
    await verify_api_key(api_key)
    try:
        return await _client().scrape_main_page()
    except Exception as e:
        logger.error("Error scraping webconsole: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/bandwidth/set")
async def set_bandwidth(
    req: SetBandwidthRequest,
    api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    """Set i2pd bandwidth caps via webconsole (KB/s)."""
    await verify_api_key(api_key)
    bw = req.inbound or req.outbound or 64
    if req.inbound is not None and req.outbound is not None:
        cmd = f"set_bw&in={max(1, req.inbound)}&out={max(1, req.outbound)}"
    else:
        val = max(1, bw)
        cmd = f"set_bw&bw={val}"
    try:
        await _client().run_webconsole_command(cmd)
        logger.info("Bandwidth set via webconsole: %s", cmd)
        return {"status": "ok", "inbound": req.inbound or bw, "outbound": req.outbound or bw}
    except Exception as e:
        logger.error("Error setting bandwidth: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/commands")
async def list_commands(api_key: Optional[str] = Header(None, alias="x-api-key")):
    await verify_api_key(api_key)
    return {"commands": await _client().get_commands()}


@app.post("/api/command/{cmd_id}")
async def run_command(
    cmd_id: str,
    api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    await verify_api_key(api_key)
    try:
        await _client().run_webconsole_command(cmd_id)
        return {"status": "ok", "command": cmd_id}
    except Exception as e:
        logger.error("Error running command %s: %s", cmd_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/transports")
async def get_transports(api_key: Optional[str] = Header(None, alias="x-api-key")):
    await verify_api_key(api_key)
    try:
        return {"transports": [t.model_dump() for t in await _client().scrape_transports()]}
    except Exception as e:
        logger.error("Error fetching transports: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/local-destinations")
async def get_local_destinations(api_key: Optional[str] = Header(None, alias="x-api-key")):
    await verify_api_key(api_key)
    try:
        return {"destinations": [d.model_dump() for d in await _client().scrape_local_destinations()]}
    except Exception as e:
        logger.error("Error fetching local destinations: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/router-health")
async def get_router_health(api_key: Optional[str] = Header(None, alias="x-api-key")):
    """Comprehensive router health assessment with a 0-100 health score."""
    await verify_api_key(api_key)
    c = _client()
    try:
        i2p_data = await c.i2p_router_info({
            "i2p.router.uptime": "",
            "i2p.router.netdb.activepeers": "",
            "i2p.router.net.tunnels.inbound": "",
            "i2p.router.net.tunnels.outbound": "",
            "i2p.router.status": "",
            "i2p.router.net.bw.inbound.1s": "",
            "i2p.router.net.bw.outbound.1s": "",
        })
        uptime = int(i2p_data.get("i2p.router.uptime", 0)) // 1000
        active_peers = int(i2p_data.get("i2p.router.netdb.activepeers", 0))
        tunnels_in = int(i2p_data.get("i2p.router.net.tunnels.inbound", 0))
        tunnels_out = int(i2p_data.get("i2p.router.net.tunnels.outbound", 0))
        bw_in = float(i2p_data.get("i2p.router.net.bw.inbound.1s", 0))
        bw_out = float(i2p_data.get("i2p.router.net.bw.outbound.1s", 0))
        online = active_peers > 0

        details = await c.scrape_main_page()
        success_rate = details.tunnel_success_rate
        floodfills = details.floodfills
        routers_known = details.routers
        leasesets = details.leasesets
        network_status = details.network_status

        score = 0.0
        if online:
            score += 20
        score += min(active_peers / 5, 20)
        score += min((tunnels_in + tunnels_out) / 2, 20)
        score += success_rate / 5

        if uptime > 3600:
            score += 10
        elif uptime > 600:
            score += 5
        else:
            score += 2

        if floodfills > 0:
            score += 5
        if routers_known > 10:
            score += 5

        score = min(round(score, 1), 100.0)

        return {
            "status": "online" if active_peers > 0 else "connecting",
            "health_score": score,
            "uptime_seconds": uptime,
            "active_peers": active_peers,
            "tunnels": {"inbound": tunnels_in, "outbound": tunnels_out, "total": tunnels_in + tunnels_out},
            "bandwidth": {"inbound_kbps": round(bw_in, 1), "outbound_kbps": round(bw_out, 1)},
            "network": {
                "status": network_status,
                "routers_known": routers_known,
                "floodfills": floodfills,
                "leasesets": leasesets,
                "tunnel_success_rate_pct": success_rate,
            },
            "flags": {
                "floodfill": "F" in details.caps,
                "reachable": "R" in details.caps,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching router health: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/config")
async def get_config(api_key: Optional[str] = Header(None, alias="x-api-key")):
    await verify_api_key(api_key)
    return {"poll_interval": POLL_INTERVAL, "api_version": "1.0.0"}


# ── Stub endpoints for Abyssal crawler (proxied through Prism nginx) ──
# The Prism React dashboard expects these endpoints. They're handled by
# the Abyssal backend directly, but when accessed through Prism's /api/
# prefix they hit this router. Return safe empty responses.

@app.get("/api/crawl/jobs")
async def crawl_jobs_stub(api_key: Optional[str] = Header(None, alias="x-api-key")):
    return []

@app.post("/api/crawl/start")
async def crawl_start_stub(api_key: Optional[str] = Header(None, alias="x-api-key")):
    return {"job_id": 0, "status": "not_available"}

@app.get("/api/crawl/jobs/{job_id}")
async def crawl_job_stub(job_id: int, api_key: Optional[str] = Header(None, alias="x-api-key")):
    return {"id": job_id, "status": "unknown", "url": "", "max_pages": 0, "max_depth": 0, "pages_crawled": 0}

@app.post("/api/crawl/jobs/{job_id}/pause")
async def crawl_pause_stub(job_id: int, api_key: Optional[str] = Header(None, alias="x-api-key")):
    return {"status": "paused"}

@app.post("/api/crawl/jobs/{job_id}/resume")
async def crawl_resume_stub(job_id: int, api_key: Optional[str] = Header(None, alias="x-api-key")):
    return {"status": "resumed"}

@app.post("/api/crawl/jobs/{job_id}/rerun")
async def crawl_rerun_stub(job_id: int, api_key: Optional[str] = Header(None, alias="x-api-key")):
    return {"job_id": 0, "status": "not_available"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
