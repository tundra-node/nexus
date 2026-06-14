import base64
import hashlib
import logging
import re
import urllib.parse

import httpx

from abyssal.config import I2PD_HTTP_PROXY

logger = logging.getLogger(__name__)

JUMP_SERVICES = [
    {
        "url": "http://7tbay5p4kzeekxvyvbf6v7eauazemsnnl2aoyqhg5jzpr5eke7tq.b32.i2p/cgi-bin/jump.cgi",
        "param": "a",
    },
    {
        "url": "http://nytzrhrjjfsutowojvxi7hphesskpqqr65wpistz6wa7cpajhp7a.b32.i2p/cgi-bin/jump.cgi",
        "param": "q",
    },
    {
        "url": "http://shx5vqsw7usdaunyzr2qmes2fq37oumybpudrd4jjj4e4vk4uusa.b32.i2p/jump/",
        "param": None,
    },
]


def _b32_from_dest(dest_b64: str) -> str:
    try:
        raw = base64.b64decode(dest_b64)
        h = hashlib.sha256(raw).digest()
        b32 = base64.b32encode(h).decode("ascii").lower().replace("=", "")
        return b32
    except Exception as e:
        logger.debug("Failed to compute b32 from destination: %s", e)
        return ""


def _extract_helper_from_html(html: str, hostname: str):
    m = re.search(
        r'i2paddresshelper=([a-zA-Z0-9_\-~%]+)',
        html,
    )
    if m:
        raw = m.group(1)
        decoded = urllib.parse.unquote(raw)
        return decoded

    m = re.search(
        rf'href="[^"]*hostname={re.escape(hostname)}[^"]*"',
        html
    )
    if m:
        return None

    return None


async def resolve_host(hostname: str, http_proxy: str = I2PD_HTTP_PROXY):
    if not hostname.endswith(".i2p"):
        hostname += ".i2p"

    for js in JUMP_SERVICES:
        try:
            if js["param"]:
                url = f"{js['url']}?{js['param']}={hostname}"
            else:
                url = f"{js['url']}{hostname}"

            async with httpx.AsyncClient(proxy=http_proxy, timeout=30.0) as client:
                resp = await client.get(url, headers={"User-Agent": "Abyssal-Crawler/1.0"})
                if resp.status_code != 200:
                    continue

                html = resp.text
                helper = _extract_helper_from_html(html, hostname)
                if not helper:
                    continue

                b32 = _b32_from_dest(helper)
                if b32:
                    return {"b32": b32, "address_helper": helper}

        except Exception as e:
            logger.debug("Jump service %s failed for %s: %s", js.get("url"), hostname, e)
            continue

    logger.debug("All jump services failed to resolve %s", hostname)
    return None
