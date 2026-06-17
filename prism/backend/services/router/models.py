"""
Prism Router API — Pydantic models for all API responses.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel


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
    tunnels: List[TunnelEntry]
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


class SetBandwidthRequest(BaseModel):
    inbound: Optional[int] = None
    outbound: Optional[int] = None
