"""
Prism API — Router Dashboard Service
Status, bandwidth, tunnels, router info, commands, transports, destinations.
"""

import asyncio
import html as html_lib
import httpx
import logging
import re
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from common.config import API_KEY, I2PD_API_URL, I2PD_PASSWORD, WEBCONSOLE_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

POLL_INTERVAL = 1

# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class StatusResponse(BaseModel):
    uptime: int
    active_peers: int
    tunnel_count: int
    tunnels_in: int
    tunnels_out: int
    status: str

class BandwidthResponse(BaseModel):
    inbound_rate: float
    outbound_rate: float
    total_inbound: int
    total_outbound: int

class TunnelEntry(BaseModel):
    id: str
    state: str
    direction: str
    latency_ms: int = 0
    data_kib: float = 0.0

class TunnelsResponse(BaseModel):
    tunnels: list[TunnelEntry]
    total: int

class RouterInfoResponse(BaseModel):
    version: str
    identity: str
    uptime: int
    net_id: int

class RouterDetailsResponse(BaseModel):
    identity: str
    caps: str
    version: str
    external_address: str
    routers: int
    floodfills: int
    leasesets: int
    client_tunnels: int
    transit_tunnels: int
    network_status: str
    tunnel_success_rate: int
    uptime: str
    received: str
    sent: str
    transit: str
    services: Dict[str, str]

class TransportInfo(BaseModel):
    name: str
    peers: int

class I2pTunnelDestination(BaseModel):
    name: str
    b32: str

# ---------------------------------------------------------------------------
# App
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
# Caches
# ---------------------------------------------------------------------------

class BandwidthCache:
    def __init__(self):
        self.last_inbound = 0.0
        self.last_outbound = 0.0
        self.total_inbound = 0
        self.total_outbound = 0

bandwidth_cache = BandwidthCache()
_webconsole_token: Optional[str] = None

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

async def verify_api_key(x_api_key: Optional[str]) -> None:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing API key")
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")

# ---------------------------------------------------------------------------
# I2PControl (HTTPS JSON-RPC on port 7650)
# ---------------------------------------------------------------------------

class I2PControlSession:
    def __init__(self):
        self.token: Optional[str] = None
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(verify=False, timeout=10.0)
        return self._client

    async def authenticate(self):
        client = await self._get_client()
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "Authenticate",
            "params": {"API": 1, "Password": I2PD_PASSWORD},
        }
        response = await client.post(
            I2PD_API_URL, json=payload, headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        data = response.json()
        if data.get("error"):
            raise HTTPException(
                status_code=500, detail=f"I2PControl auth error: {data['error']}"
            )
        self.token = data["result"]["Token"]

    async def call(self, method: str, fields: Dict[str, str]) -> Dict[str, Any]:
        client = await self._get_client()
        if not self.token:
            await self.authenticate()

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": fields,
        }

        response = await client.post(
            I2PD_API_URL, json=payload, headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        data = response.json()

        if data.get("error"):
            if data["error"].get("code") in (-32001, -32700):
                await self.authenticate()
                response = await client.post(
                    I2PD_API_URL,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                data = response.json()
            if data.get("error"):
                raise HTTPException(
                    status_code=500, detail=f"I2PControl error: {data['error']}"
                )

        return data.get("result", {})

i2p = I2PControlSession()

async def i2p_router_info(fields: Dict[str, str]) -> Dict[str, Any]:
    try:
        return await i2p.call("RouterInfo", fields)
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="Unable to connect to i2pd on port 7650 (HTTPS)",
        )

# ---------------------------------------------------------------------------
# Webconsole scraping (HTTP on port 7070)
# ---------------------------------------------------------------------------

async def _fetch_webconsole(path: str = "/") -> str:
    async with httpx.AsyncClient(timeout=5.0) as c:
        # i2pd webconsole requires Host: localhost header
        r = await c.get(f"{WEBCONSOLE_URL}{path}", headers={"Host": "localhost"})
        r.raise_for_status()
        return r.text

def _parse_kv(html: str) -> Dict[str, str]:
    data = {}
    for m in re.finditer(r"<b>([^<]+?)</b>\s*:?\s*([^<\n\r]+)", html):
        key = m.group(1).strip().rstrip(":")
        val = m.group(2).strip()
        data[key] = val
    return data

def _parse_services(html: str) -> Dict[str, str]:
    services = {}
    for m in re.finditer(
        r"<tr><td>([^<]+)</td><td\s+class='(\w+)'>(Enabled|Disabled)</td></tr>", html
    ):
        services[m.group(1)] = m.group(3).lower()
    return services

def _parse_tunnel_list(html: str, direction: str) -> list[TunnelEntry]:
    tunnels = []
    section = re.search(
        rf"<b>{direction} tunnels:</b><br>(.*?)(?:<b>|$)", html, re.DOTALL
    )
    if not section:
        return tunnels

    content = section.group(1)
    items = re.findall(r'<div class="listitem">(.*?)</div>', content, re.DOTALL)

    for item in items:
        text = html_lib.unescape(item)
        text = re.sub(r"<[^>]+>", " ", text).strip()

        state = "unknown"
        if "established" in text:
            state = "established"
        elif "expiring" in text:
            state = "expiring"
        elif "building" in text:
            state = "building"
        elif "failed" in text or "test failed" in text:
            state = "failed"

        tid = "unknown"
        m_id = re.search(r"(\d+):me", text)
        if m_id:
            tid = m_id.group(1)

        latency = 0
        m_lat = re.search(r"\(\s*(\d+)\s*ms\s*\)", text)
        if m_lat:
            latency = int(m_lat.group(1))

        data_kib = 0.0
        m_data = re.search(r"(\d+\.\d+)\s*KiB", text)
        if m_data:
            data_kib = float(m_data.group(1))

        tunnels.append(
            TunnelEntry(
                id=tid,
                state=state,
                direction=direction.lower(),
                latency_ms=latency,
                data_kib=data_kib,
            )
        )
    return tunnels

async def scrape_main_page() -> RouterDetailsResponse:
    html = await _fetch_webconsole("/")
    kv = _parse_kv(html)

    ident_m = re.search(r"<b>Router Ident:?\s*</b>\s*([^<\s]+)", html)
    caps_m = re.search(r"<b>Router Caps:?\s*</b>\s*([^<\s]+)", html)
    ext_html = re.search(r"<b>Our external address:?\s*</b><br>\s*(<table class=\"extaddr\">.*?</table>)", html, re.DOTALL)
    version_m = re.search(r"<b>Version:?\s*</b>\s*([^<\s]+)", html)
    external = "unknown"
    if ext_html:
        parts = re.findall(r"<td[^>]*>([^<]+)</td>", ext_html.group(1))
        if len(parts) >= 4:
            external = f"{parts[0]} {parts[1].strip()}, {parts[2]} {parts[3].strip()}"

    identity = ident_m.group(1).strip() if ident_m else "unknown"
    caps = caps_m.group(1).strip() if caps_m else "?"
    version = version_m.group(1).strip() if version_m else kv.get("Version", "unknown")

    return RouterDetailsResponse(
        identity=identity,
        caps=caps,
        version=version,
        external_address=external,
        routers=int(re.search(r"Routers:</b>\s*(\d+)", html).group(1)) if re.search(r"Routers:</b>\s*(\d+)", html) else 0,
        floodfills=int(re.search(r"Floodfills:</b>\s*(\d+)", html).group(1)) if re.search(r"Floodfills:</b>\s*(\d+)", html) else 0,
        leasesets=int(re.search(r"LeaseSets:</b>\s*(\d+)", html).group(1)) if re.search(r"LeaseSets:</b>\s*(\d+)", html) else 0,
        client_tunnels=int(re.search(r"Client Tunnels:</b>\s*(\d+)", html).group(1)) if re.search(r"Client Tunnels:</b>\s*(\d+)", html) else 0,
        transit_tunnels=int(re.search(r"Transit Tunnels[:\s]*</b>\s*(\d+)", html).group(1)) if re.search(r"Transit Tunnels[:\s]*</b>\s*(\d+)", html) else int(kv.get("Transit Tunnels", "0").strip() or "0"),
        network_status=kv.get("Network status", "unknown"),
        tunnel_success_rate=int(kv.get("Tunnel creation success rate", "0").replace("%", "")),
        uptime=kv.get("Uptime", ""),
        received=kv.get("Received", ""),
        sent=kv.get("Sent", ""),
        transit=kv.get("Transit", ""),
        services=_parse_services(html),
    )

async def scrape_tunnels_page() -> list[TunnelEntry]:
    html = await _fetch_webconsole("/?page=tunnels")
    inbound = _parse_tunnel_list(html, "Inbound")
    outbound = _parse_tunnel_list(html, "Outbound")
    return inbound + outbound

async def scrape_transports() -> list[TransportInfo]:
    html = await _fetch_webconsole("/?page=transports")
    transports = []
    for m in re.finditer(
        r"<label[^>]*><b>(\w+)</b>[^<]*\([^\d]*(\d+)", html
    ):
        transports.append(TransportInfo(name=m.group(1), peers=int(m.group(2))))
    return transports

async def scrape_local_destinations() -> list[I2pTunnelDestination]:
    html = await _fetch_webconsole("/?page=i2p_tunnels")
    dests = []
    seen = set()
    for m in re.finditer(
        r'href="[^"]*b32=([a-z0-9]+)"[^>]*>([^<]+)</a>\s*&#8656;\s*[a-z0-9]+\.b32\.i2p',
        html,
    ):
        b32 = m.group(1)
        name = m.group(2).strip()
        if b32 not in seen:
            seen.add(b32)
            dests.append(I2pTunnelDestination(name=name, b32=b32))
    return dests

async def get_webconsole_token() -> str:
    global _webconsole_token
    html = await _fetch_webconsole("/?page=commands")
    m = re.search(r"token=(\d+)", html)
    if m:
        _webconsole_token = m.group(1)
    return _webconsole_token or ""

async def run_webconsole_command(cmd: str) -> str:
    token = await get_webconsole_token()
    async with httpx.AsyncClient(timeout=5.0) as c:
        r = await c.get(f"{WEBCONSOLE_URL}/?cmd={cmd}&token={token}", headers={"Host": "localhost"})
        return r.text

async def _scrape_commands() -> list[dict]:
    html = await _fetch_webconsole("/?page=commands")
    commands = []
    seen = set()
    for m in re.finditer(r'href="[^"]*\?cmd=([^"&]+)[^"]*">([^<]+)</a>', html):
        cmd_id = m.group(1)
        label = m.group(2).strip()
        if cmd_id not in seen and label:
            seen.add(cmd_id)
            commands.append({"id": cmd_id, "label": label})
    return commands

_commands_cache = None
_commands_cache_ts = 0.0

async def get_commands() -> list[dict]:
    import time
    global _commands_cache, _commands_cache_ts
    now = time.time()
    if _commands_cache and now - _commands_cache_ts < 30:
        return _commands_cache
    try:
        cmds = await _scrape_commands()
        _commands_cache = cmds
        _commands_cache_ts = now
        return cmds
    except Exception:
        return _commands_cache or []

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
        data = await i2p_router_info({
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
    try:
        data = await i2p_router_info({
            "i2p.router.net.bw.inbound.1s": "",
            "i2p.router.net.bw.outbound.1s": "",
            "i2p.router.net.bw.inbound.15s": "",
            "i2p.router.net.bw.outbound.15s": "",
        })
        inbound_rate = float(data.get("i2p.router.net.bw.inbound.1s", 0))
        outbound_rate = float(data.get("i2p.router.net.bw.outbound.1s", 0))
        bandwidth_cache.total_inbound += int(inbound_rate)
        bandwidth_cache.total_outbound += int(outbound_rate)
        return BandwidthResponse(
            inbound_rate=inbound_rate,
            outbound_rate=outbound_rate,
            total_inbound=bandwidth_cache.total_inbound,
            total_outbound=bandwidth_cache.total_outbound,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching bandwidth: %s", e)
        return BandwidthResponse(
            inbound_rate=0, outbound_rate=0,
            total_inbound=bandwidth_cache.total_inbound,
            total_outbound=bandwidth_cache.total_outbound,
        )

@app.get("/api/tunnels", response_model=TunnelsResponse)
async def get_tunnels(api_key: Optional[str] = Header(None, alias="x-api-key")):
    await verify_api_key(api_key)
    try:
        try:
            entries = await scrape_tunnels_page()
            if entries:
                return TunnelsResponse(tunnels=entries, total=len(entries))
        except Exception:
            pass
        data = await i2p_router_info({
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
        data = await i2p_router_info({"i2p.router.version": "", "i2p.router.uptime": ""})
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

@app.get("/api/router-details", response_model=RouterDetailsResponse)
async def get_router_details(api_key: Optional[str] = Header(None, alias="x-api-key")):
    await verify_api_key(api_key)
    try:
        return await scrape_main_page()
    except Exception as e:
        logger.error("Error scraping webconsole: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

class SetBandwidthRequest(BaseModel):
    inbound: Optional[int] = None
    outbound: Optional[int] = None

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
        await run_webconsole_command(cmd)
        logger.info("Bandwidth set via webconsole: %s", cmd)
        return {"status": "ok", "inbound": req.inbound or bw, "outbound": req.outbound or bw}
    except Exception as e:
        logger.error("Error setting bandwidth: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/commands")
async def list_commands(api_key: Optional[str] = Header(None, alias="x-api-key")):
    await verify_api_key(api_key)
    return {"commands": await get_commands()}

@app.post("/api/command/{cmd_id}")
async def run_command(
    cmd_id: str,
    api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    await verify_api_key(api_key)
    try:
        await run_webconsole_command(cmd_id)
        return {"status": "ok", "command": cmd_id}
    except Exception as e:
        logger.error("Error running command %s: %s", cmd_id, e)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/transports")
async def get_transports(api_key: Optional[str] = Header(None, alias="x-api-key")):
    await verify_api_key(api_key)
    try:
        return {"transports": await scrape_transports()}
    except Exception as e:
        logger.error("Error fetching transports: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/local-destinations")
async def get_local_destinations(api_key: Optional[str] = Header(None, alias="x-api-key")):
    await verify_api_key(api_key)
    try:
        return {"destinations": await scrape_local_destinations()}
    except Exception as e:
        logger.error("Error fetching local destinations: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/router-health")
async def get_router_health(api_key: Optional[str] = Header(None, alias="x-api-key")):
    """Comprehensive router health assessment with a 0-100 health score."""
    await verify_api_key(api_key)
    try:
        i2p_data = await i2p_router_info({
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

        details = await scrape_main_page()
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
