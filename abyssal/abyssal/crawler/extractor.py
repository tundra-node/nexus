import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .fetcher import normalize_url


def extract_links(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("#") or href.startswith("javascript:"):
            continue
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in ("http", "https"):
            continue
        normalized = normalize_url(absolute)
        if normalized not in seen:
            seen.add(normalized)
            links.append(normalized)
    return links


def extract_title(html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else ""


def extract_text_content(html: str, max_chars: int = 5000) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    return text[:max_chars]


def extract_canonical(soup: BeautifulSoup, base_url: str) -> str:
    link = soup.find("link", rel="canonical")
    if link and link.get("href"):
        return urljoin(base_url, link["href"])
    return ""


def extract_meta(soup: BeautifulSoup) -> dict:
    meta: dict[str, str] = {}
    for tag in soup.find_all("meta"):
        name = (tag.get("name") or tag.get("property") or "").lower()
        content = (tag.get("content") or "").strip()
        if name == "description":
            meta["description"] = content[:300]
        elif name == "keywords":
            meta["keywords"] = content[:500]
        elif name == "og:site_name":
            meta["og_site_name"] = content[:200]
    return meta
