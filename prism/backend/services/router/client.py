"""
Prism Router API — I2PControl client + webconsole scraper.

Handles:
- I2PControl JSON-RPC (HTTPS port 7650) for status, bandwidth, etc.
- i2pd webconsole HTTP scraping (port 7070) for tunnels, transports, etc.
"""

import html as html_lib
import logging
import re
import time
from typing import Dict, Any, List, Optional

import httpx
from fastapi import HTTPException

from common.config import I2PD_API_URL, I2PD_PASSWORD, WEBCONSOLE_URL
from .models import (
    RouterDetailsResponse,
    TunnelEntry,
    TransportInfo,
    I2pTunnelDestination,
)

logger = logging.getLogger(__name__)

_webconsole_token: Optional[str] = None
_commands_cache: Optional[List[dict]] = None
_commands_cache_ts: float = 0.0


class BandwidthCache:
    def __init__(self):
        self.last_inbound = 0.0
        self.last_outbound = 0.0
        self.total_inbound = 0
        self.total_outbound = 0


bandwidth_cache = BandwidthCache()


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

        params = {**fields}
        if self.token:
            params["Token"] = self.token

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
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
# Webconsole scraping (HTTP port 7070)
# ---------------------------------------------------------------------------

async def _fetch_webconsole(path: str = "/") -> str:
    async with httpx.AsyncClient(timeout=5.0) as c:
        r = await c.get(f"{WEBCONSOLE_URL}{path}", headers={"Host": "localhost"})
        r.raise_for_status()
        return r.text


def _parse_kv(html: str) -> Dict[str, str]:
    data: Dict[str, str] = {}
    for m in re.finditer(r"<b>([^<]+?)</b>\s*:?\s*([^<\n\r]+)", html):
        key = m.group(1).strip().rstrip(":")
        val = m.group(2).strip()
        data[key] = val
    return data


def _parse_services(html: str) -> Dict[str, str]:
    services: Dict[str, str] = {}
    for m in re.finditer(
        r"<tr><td>([^<]+)</td><td\s+class='(\w+)'>(Enabled|Disabled)</td></tr>", html
    ):
        services[m.group(1)] = m.group(3).lower()
    return services


def _parse_tunnel_list(html: str, direction: str) -> List[TunnelEntry]:
    tunnels: List[TunnelEntry] = []
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
    ext_html = re.search(
        r"<b>Our external address:?\s*</b><br>\s*(<table class=\"extaddr\">.*?</table>)",
        html,
        re.DOTALL,
    )
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
        routers=(
            int(re.search(r"Routers:</b>(\d+)", html).group(1))
            if re.search(r"Routers:</b>(\d+)", html)
            else 0
        ),
        floodfills=(
            int(re.search(r"Floodfills:</b>(\d+)", html).group(1))
            if re.search(r"Floodfills:</b>(\d+)", html)
            else 0
        ),
        leasesets=(
            int(re.search(r"LeaseSets:</b>(\d+)", html).group(1))
            if re.search(r"LeaseSets:</b>(\d+)", html)
            else 0
        ),
        client_tunnels=(
            int(re.search(r"Client Tunnels:</b>(\d+)", html).group(1))
            if re.search(r"Client Tunnels:</b>(\d+)", html)
            else 0
        ),
        transit_tunnels=(
            int(re.search(r"Transit Tunnels[:\s]*</b>(\d+)", html).group(1))
            if re.search(r"Transit Tunnels[:\s]*</b>(\d+)", html)
            else int(kv.get("Transit Tunnels", "0").strip() or "0")
        ),
        network_status=kv.get("Network status", "unknown"),
        tunnel_success_rate=int(kv.get("Tunnel creation success rate", "0").replace("%", "")),
        uptime=kv.get("Uptime", ""),
        received=kv.get("Received", ""),
        sent=kv.get("Sent", ""),
        transit=kv.get("Transit", ""),
        services=_parse_services(html),
    )


async def scrape_tunnels_page() -> List[TunnelEntry]:
    html = await _fetch_webconsole("/?page=tunnels")
    inbound = _parse_tunnel_list(html, "Inbound")
    outbound = _parse_tunnel_list(html, "Outbound")
    return inbound + outbound


async def scrape_transports() -> List[TransportInfo]:
    html = await _fetch_webconsole("/?page=transports")
    transports: List[TransportInfo] = []
    for m in re.finditer(
        r"<label[^>]*><b>(\w+)</b>[^<]*\([^\d]*(\d+)", html
    ):
        transports.append(TransportInfo(name=m.group(1), peers=int(m.group(2))))
    return transports


async def scrape_local_destinations() -> List[I2pTunnelDestination]:
    html = await _fetch_webconsole("/?page=i2p_tunnels")
    dests: List[I2pTunnelDestination] = []
    seen: set = set()
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
        r = await c.get(
            f"{WEBCONSOLE_URL}/",
            params={"cmd": cmd, "token": token},
            headers={"Host": "localhost"},
        )
        return r.text


async def _scrape_commands() -> List[dict]:
    html = await _fetch_webconsole("/?page=commands")
    commands: List[dict] = []
    seen: set = set()
    for m in re.finditer(r'href="[^"]*\?cmd=([^"&]+)[^"]*">([^<]+)</a>', html):
        cmd_id = m.group(1)
        label = m.group(2).strip()
        if cmd_id not in seen and label:
            seen.add(cmd_id)
            commands.append({"id": cmd_id, "label": label})
    return commands


async def get_commands() -> List[dict]:
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
