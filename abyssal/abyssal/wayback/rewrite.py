from __future__ import annotations

import logging
import re
import urllib.parse
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from abyssal.config import PROXY_TOKEN

logger = logging.getLogger(__name__)

_RESOURCE_ATTRS = [
    ("img", "src"),
    ("script", "src"),
    ("source", "src"),
    ("video", "src"),
    ("audio", "src"),
    ("iframe", "src"),
    ("link", "href"),
    ("object", "data"),
    ("embed", "src"),
]


def _resolve_css_urls(css_text: str, base_url: str) -> str:
    def _abs(m: re.Match) -> str:
        raw = m.group(1) or m.group(2) or m.group(3)
        raw = raw.strip().strip("'\"")
        if raw.startswith("data:") or raw.startswith("http://") or raw.startswith("https://") or raw.startswith("//"):
            return m.group(0)
        absolute = urllib.parse.urljoin(base_url, raw)
        quote = ""
        if m.group(2) is not None:
            quote = "'" if raw.startswith("'") else '"'
        return f"url({quote}{absolute}{quote})"

    pattern = r'url\(\s*([^\s\'"()]+)\s*\)|url\(\s*\'([^\']+)\'\s*\)|url\(\s*"([^"]+)"\s*\)'
    return re.sub(pattern, _abs, css_text)


async def _fetch_and_inline_css(href: str, base_url: str, http_proxy: str) -> Optional[str]:
    css_url = urllib.parse.urljoin(base_url, href)
    try:
        async with httpx.AsyncClient(proxy=http_proxy, timeout=60.0) as client:
            resp = await client.get(
                css_url,
                headers={"User-Agent": "Abyssal-Wayback/1.0", "Accept": "text/css,*/*"},
            )
            resp.raise_for_status()
            css_text = resp.text
            css_text = _resolve_css_urls(css_text, css_url)

            def _resolve_import(m: re.Match) -> str:
                import_url = m.group(1) or m.group(2) or m.group(3)
                if not import_url:
                    return m.group(0)
                imported = _resolve_css_urls(import_url, css_url)
                imported_content = None
                try:
                    r = httpx.get(imported, proxy=http_proxy, timeout=30.0, headers={"User-Agent": "Abyssal-Wayback/1.0"})
                    r.raise_for_status()
                    imported_content = _resolve_css_urls(r.text, imported)
                except Exception as e:
                    logger.warning("Failed to fetch @import %s: %s", imported, e)
                if imported_content:
                    return f"/* @import from {import_url} */\n{imported_content}"
                return m.group(0)

            import_pattern = r'@import\s+url\(\s*([^\s\'"()]+)\s*\)|@import\s+url\(\s*\'([^\']+)\'\s*\)|@import\s+url\(\s*"([^"]+)"\s*\)|@import\s+\'([^\']+)\'|@import\s+"([^"]+)"'
            css_text = re.sub(import_pattern, _resolve_import, css_text)
            return css_text
    except Exception as e:
        logger.warning("Failed to fetch CSS %s: %s", css_url, e)
        return None


async def inline_css(html: str, base_url: str, http_proxy: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    changed = False

    for link_tag in soup.find_all("link", rel=lambda v: v and "stylesheet" in (v if isinstance(v, str) else " ".join(v))):
        href = link_tag.get("href")
        if not href:
            continue
        if link_tag.get("rel") and "alternate" in (link_tag["rel"] if isinstance(link_tag["rel"], list) else [link_tag["rel"]]):
            continue
        if href.startswith("data:"):
            continue

        css_content = await _fetch_and_inline_css(href, base_url, http_proxy)
        if css_content:
            style_tag = soup.new_tag("style")
            style_tag.string = f"\n/* Inlined from {href} */\n{css_content}\n"
            link_tag.replace_with(style_tag)
            changed = True
            logger.info("Inlined CSS: %s (%d chars)", href, len(css_content))

    if changed:
        return str(soup)
    return html


def _rewrite_css_urls(css_text: str, base_url: str, proxy_base: str) -> str:
    def _proxy_css_url(m: re.Match) -> str:
        raw = m.group(1) or m.group(2) or m.group(3)
        if not raw:
            return m.group(0)
        raw = raw.strip().strip("'\"")
        if raw.startswith("data:") or raw.startswith("#") or raw.startswith("http://") or raw.startswith("https://"):
            absolute = raw
        else:
            absolute = urllib.parse.urljoin(base_url, raw)
        if absolute.startswith("/api/browser/proxy"):
            return m.group(0)
        proxied = proxy_base + urllib.parse.quote(absolute, safe="")
        return f"url({proxied})"

    pattern = r'url\(\s*([^\s\'"()]+)\s*\)|url\(\s*\'([^\']+)\'\s*\)|url\(\s*"([^"]+)"\s*\)'
    return re.sub(pattern, _proxy_css_url, css_text)


def rewrite_external_urls(html: str, base_url: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    proxy_base = f"/api/browser/proxy?token={PROXY_TOKEN}&url="

    def _proxy_url(url: str) -> str:
        if not url or url.startswith("#") or url.startswith("javascript:") or url.startswith("data:"):
            return url
        absolute = urllib.parse.urljoin(base_url, url)
        return proxy_base + urllib.parse.quote(absolute, safe="")

    for tag, attr in _RESOURCE_ATTRS:
        for el in soup.find_all(tag, **{attr: True}):
            el[attr] = _proxy_url(el[attr])

    for style_tag in soup.find_all("style"):
        if style_tag.string:
            style_tag.string = _rewrite_css_urls(style_tag.string, base_url, proxy_base)

    return str(soup)
