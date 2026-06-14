import logging
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_SCRIPT_RANGES: list[tuple[range, str]] = [
    (range(0x0400, 0x0500), "ru"),
    (range(0x0500, 0x0530), "ru"),
    (range(0x2DE0, 0x2E00), "ru"),
    (range(0x3040, 0x3100), "ja"),
    (range(0x4E00, 0xA000), "zh"),
    (range(0x0600, 0x0700), "ar"),
    (range(0x0750, 0x0800), "ar"),
    (range(0xAC00, 0xD7B0), "ko"),
    (range(0x0E00, 0x0F00), "th"),
    (range(0x0370, 0x0400), "el"),
    (range(0x0590, 0x0600), "he"),
    (range(0x0900, 0x0980), "hi"),
]

_STOPWORDS: dict[str, set[str]] = {
    "en": {"the", "and", "for", "are", "but", "not", "you", "all", "can",
           "was", "one", "our", "out", "has", "have", "been", "this", "that",
           "with", "from", "they", "what", "when", "where", "which", "their",
           "there", "about", "would", "could", "should", "then", "some", "them",
           "these", "into", "more", "your", "its", "than", "over", "such",
           "only", "other", "after", "just", "very", "because", "each", "most",
           "many", "between", "also", "well", "back", "even", "down", "like"},
    "de": {"der", "die", "das", "und", "ist", "mit", "auf", "für", "bei",
           "nicht", "sich", "ein", "eine", "einen", "einer", "dem", "den",
           "des", "zu", "von", "aus", "nach", "vor", "durch", "über", "an",
           "werden", "wird", "sind", "auch", "oder", "um", "als", "wie",
           "zum", "zur", "im", "am", "haben", "hat", "seine", "seiner",
           "ihre", "ihrer", "dieser", "diese", "dieses", "dann", "doch",
           "noch", "schon", "nur", "aber", "alle", "kann", "kein", "keine",
           "sehr", "wurde", "worden", "wären", "hätten", "können"},
    "fr": {"le", "la", "les", "des", "est", "pas", "pour", "dans", "avec",
           "sur", "tout", "sont", "mais", "plus", "cette", "aussi", "leur",
           "ils", "elle", "entre", "sans", "depuis", "chez", "pendant",
           "quand", "comme", "très", "tous", "toute", "deux", "peut",
           "faire", "bien", "avoir", "autre", "chaque", "avant", "après",
           "encore", "alors", "donc", "même", "votre", "notre", "voici",
           "voilà", "peu", "mon", "ton", "son", "leur", "où", "parce"},
    "es": {"el", "la", "los", "las", "del", "por", "con", "para", "como",
           "más", "pero", "sus", "una", "este", "esta", "entre", "tiene",
           "todo", "parte", "tiempo", "cada", "también", "desde", "hasta",
           "durante", "según", "contra", "antes", "después", "siempre",
           "nunca", "mismo", "otro", "donde", "quien", "cual", "cuando",
           "muchos", "poco", "gran", "mayor", "mejor", "además", "incluso",
           "forma", "valor", "sobre", "entre", "tras", "cerca"},
    "pt": {"o", "a", "os", "as", "do", "da", "em", "com", "para", "por",
           "mais", "como", "dos", "das", "uma", "seu", "sua", "ser", "tem",
           "era", "muito", "foi", "pode", "estar", "após", "antes", "entre",
           "cada", "depois", "maior", "menos", "mesmo", "outro", "onde",
           "quem", "tudo", "sobre", "ainda", "também", "através", "contra"},
    "nl": {"de", "het", "een", "van", "met", "voor", "niet", "zijn", "ook",
           "als", "bij", "nog", "naar", "dan", "dat", "die", "dit", "wordt",
           "heeft", "maar", "worden", "kunnen", "moeten", "tussen", "zonder",
           "tot", "uit", "door", "over", "op", "aan", "onder", "al", "geen",
           "om", "hun", "hem", "haar", "deze", "elke", "reeds", "veel"},
    "it": {"il", "la", "le", "gli", "del", "con", "per", "che", "sono",
           "una", "come", "dei", "delle", "degli", "sul", "sulla", "sulle",
           "sugli", "nel", "nella", "nelle", "negli", "allo", "alla", "agli",
           "alle", "col", "dalla", "dai", "dalle", "questa", "questo",
           "queste", "questi", "anche", "molto", "dopo", "prima", "sempre"},
    "sv": {"och", "det", "som", "en", "att", "är", "med", "för", "inte",
           "om", "ett", "till", "kan", "den", "har", "men", "från", "vid",
           "eller", "var", "de", "av", "på", "sin", "sina", "sitt", "deras",
           "dess", "över", "under", "mellan", "genom", "utan", "även", "bara"},
    "pl": {"i", "w", "na", "z", "do", "się", "nie", "to", "jest", "że",
           "ma", "ją", "mu", "go", "ich", "przy", "pod", "nad", "przez",
           "oraz", "ale", "lub", "tym", "tej", "tego", "tych", "który",
           "która", "które", "może", "być", "było", "była", "mają", "jego"},
    "nb": {"og", "det", "som", "en", "er", "med", "for", "til", "ikke",
           "om", "ett", "kan", "den", "har", "men", "fra", "ved", "eller",
           "var", "de", "av", "på", "sin", "sine", "sitt", "deres", "dens",
           "over", "under", "mellom", "uten", "også", "bare", "blir", "ble"},
    "fi": {"ja", "on", "ei", "se", "ovat", "ole", "myös", "sen", "hän",
           "mutta", "oli", "voi", "kanssa", "joka", "ovat", "tai", "kun",
           "sillä", "vain", "sitten", "vielä", "pitää", "sama", "tästä",
           "siitä", "tästä", "tähän", "välillä", "ilman", "aikana", "alue"},
}


def _detect_script(text: str) -> str:
    if not text:
        return ""
    counts: dict[str, int] = {}
    for ch in text:
        cp = ord(ch)
        for r, lang in _SCRIPT_RANGES:
            if cp in r:
                counts[lang] = counts.get(lang, 0) + 1
                break
    if not counts:
        return ""
    total = sum(counts.values())
    for lang, cnt in counts.items():
        if cnt / max(total, 1) > 0.3:
            if lang == "zh" and _has_japanese(text):
                return "ja"
            return lang
    return ""


def _has_japanese(text: str) -> bool:
    for ch in text:
        cp = ord(ch)
        if (0x3040 <= cp <= 0x309F) or (0x30A0 <= cp <= 0x30FF):
            return True
    return False


def _detect_latin_language(text: str) -> str:
    words = re.findall(r"[a-zA-Zà-ÿÀ-ß]+", text.lower())
    if not words:
        return ""
    scores: dict[str, int] = {}
    for w in words:
        for lang, stops in _STOPWORDS.items():
            if w in stops:
                scores[lang] = scores.get(lang, 0) + 1
    if not scores:
        return ""
    return max(scores, key=scores.get)


def detect_language(soup: BeautifulSoup) -> str:
    html_tag = soup.find("html")
    if html_tag and html_tag.get("lang"):
        return html_tag["lang"].strip().lower()[:10]

    for meta in soup.find_all("meta"):
        if meta.get("http-equiv", "").lower() == "content-language":
            val = meta.get("content", "")
            if val:
                return val.strip().lower()[:10]
        if meta.get("name", "").lower() == "language":
            val = meta.get("content", "")
            if val:
                return val.strip().lower()[:10]

    charset = ""
    for meta in soup.find_all("meta"):
        if meta.get("charset"):
            charset = meta.get("charset", "").lower()
            break
        if meta.get("http-equiv", "").lower() == "content-type":
            ct = meta.get("content", "")
            m = re.search(r"charset=([\w-]+)", ct, re.I)
            if m:
                charset = m.group(1).lower()
                break
    _CHARSET_TO_LANG = {
        "windows-1251": "ru", "koi8-r": "ru", "iso-8859-5": "ru",
        "shift_jis": "ja", "euc-jp": "ja", "iso-2022-jp": "ja",
        "gb2312": "zh", "gbk": "zh", "euc-cn": "zh", "big5": "zh",
        "euc-kr": "ko", "iso-2022-kr": "ko",
        "windows-1256": "ar", "iso-8859-6": "ar",
        "windows-1253": "el", "iso-8859-7": "el",
        "windows-1255": "he", "iso-8859-8": "he",
    }
    if charset in _CHARSET_TO_LANG:
        return _CHARSET_TO_LANG[charset]

    body = soup.find("body")
    text = body.get_text(separator=" ", strip=True) if body else ""
    if not text:
        title_tag = soup.find("title")
        if title_tag:
            text = title_tag.get_text(strip=True)
    if not text:
        return ""

    script = _detect_script(text)
    if script:
        return script

    lang = _detect_latin_language(text)
    if lang:
        return lang

    return ""


_GENERATOR_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(?i)phpBB"), "forum"),
    (re.compile(r"(?i)MediaWiki"), "wiki"),
    (re.compile(r"(?i)WordPress"), "blog"),
    (re.compile(r"(?i)Drupal"), "cms"),
    (re.compile(r"(?i)Joomla"), "cms"),
    (re.compile(r"(?i)Discourse"), "forum"),
    (re.compile(r"(?i)FluxBB|Flarum|Simple Machines|SMF"), "forum"),
    (re.compile(r"(?i)MoinMoin|DokuWiki|Tiki|BookStack"), "wiki"),
    (re.compile(r"(?i)Ghost"), "blog"),
    (re.compile(r"(?i)Hugo|Jekyll|Hexo|Pelican|Eleventy|Next\.?Gen"), "blog"),
    (re.compile(r"(?i)Syndie"), "social"),
    (re.compile(r"(?i)I2P[-\s]?Bote"), "email"),
    (re.compile(r"(?i)Magento|WooCommerce|Shopify|PrestaShop|OpenCart"), "market"),
    (re.compile(r"(?i)phpBB|myBB|bbPress|NodeBB|Vanilla"), "forum"),
]

_URL_SITE_TYPES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"/(forum|boards?|community|discussion|foro|fórum)/", re.I), "forum"),
    (re.compile(r"/(wiki|mediawiki|dokuwiki)/", re.I), "wiki"),
    (re.compile(r"/blog|/article|/post(?:/|s\b)", re.I), "blog"),
    (re.compile(r"/(shop|store|market|bazaar|tienda|kauf|boutique|цены)/", re.I), "market"),
    (re.compile(r"/(chat|irc|converse)/", re.I), "chat"),
    (re.compile(r"/(mail|email|webmail|inbox)/", re.I), "email"),
    (re.compile(r"/(search|engine|seek|buscar|suche)/", re.I), "search"),
    (re.compile(r"/(gallery|gallery2|album|fotos|flickr|photos|images?)/", re.I), "gallery"),
    (re.compile(r"/(torrent|download\w*|dl|files)/", re.I), "files"),
    (re.compile(r"/(paste|pastebin|snippet)/", re.I), "paste"),
    (re.compile(r"/(git|hg|svn|repo|source)/", re.I), "code"),
    (re.compile(r"/(tracker|stats|status|statistics|analytics)/", re.I), "stats"),
    (re.compile(r"/(radio|music|stream|audio|podcast)/", re.I), "media"),
    (re.compile(r"/(video|tube|stream)/", re.I), "media"),
    (re.compile(r"/(about|contact|imprint|team)/", re.I), "info"),
    (re.compile(r"/(docs?|help|support|faq|guide)/", re.I), "docs"),
    (re.compile(r"/(api|rest|json|xmlrpc)/", re.I), "api"),
    (re.compile(r"/(login|register|signup|auth|password)/", re.I), "auth"),
    (re.compile(r"/(news|announce)/", re.I), "news"),
]

_CONTENT_KEYWORDS: list[tuple[list[str], str]] = [
    (["forum", "topic", "reply", "viewtopic", "viewforum", "newpost",
      "bbtopic", "bbforum", "thread", "post reply"], "forum"),
    (["wiki", "edit this page", "view source", "history", "mediawiki",
      "wikitext", "wikicode", "dokuwiki", "sidebar"], "wiki"),
    (["blog", "published by", "leave a comment", "comments are closed",
      "posted on", "posted by", "entry-title", "blogger"], "blog"),
    (["buy", "cart", "checkout", "add to basket", "add to cart",
      "price", "market", "shop", "purchase", "order now", "product",
      "в корзину"], "market"),
    (["chat", "irc", "conversation", "messages", "private message",
      "send message", "online users"], "chat"),
    (["search", "search results", "results for", "found pages",
      "поиск"], "search"),
    (["login", "register", "sign up", "password", "create account",
      "forgot password", "sign in", "log in", "register"], "auth"),
    (["download", "torrent", "seed", "leech", "magnet", "file",
      "скачать"], "files"),
    (["gallery", "image", "photo", "picture", "album", "slideshow",
      "фото"], "gallery"),
    (["video", "watch", "streaming", "player", "embed", "tube"], "media"),
    (["paste", "pastebin", "snippet", "code", "source"], "paste"),
    (["email", "mail", "send message", "inbox", "compose",
      "webmail"], "email"),
    (["tracker", "stats", "statistics", "analytics", "dashboard",
      "uptime"], "stats"),
    (["git", "repository", "commit", "branch", "clone", "push",
      "pull"], "code"),
    (["radio", "music", "stream", "listen", "playlist", "podcast"], "media"),
    (["wiki", "documentation", "manual", "guide", "tutorial",
      "документация"], "docs"),
]

_OG_TYPES: dict[str, str] = {
    "website": "website",
    "article": "blog",
    "profile": "social",
    "book": "docs",
    "video.movie": "media",
    "video.episode": "media",
    "music.song": "media",
    "music.album": "media",
}


def classify_site_type(soup: BeautifulSoup, url: str) -> str:
    html_text = str(soup)
    meta_gen = ""
    og_type = ""
    application_name = ""

    for meta in soup.find_all("meta"):
        name = (meta.get("name") or "").lower()
        content = (meta.get("content") or "")
        if name == "generator":
            meta_gen = content
        if name == "og:type" or meta.get("property", "").lower() == "og:type":
            og_type = content.lower()
        if name == "application-name":
            application_name = content.lower()

    for pat, stype in _GENERATOR_PATTERNS:
        if pat.search(meta_gen):
            return stype

    if "syndie" in application_name:
        return "social"

    parsed = urlparse(url)
    for pat, stype in _URL_SITE_TYPES:
        if pat.search(parsed.path):
            return stype

    if og_type in _OG_TYPES:
        return _OG_TYPES[og_type]

    title_tag = soup.find("title")
    title_text = title_tag.get_text() if title_tag else ""
    body = soup.find("body")
    body_text = body.get_text(separator=" ", strip=True)[:2000].lower() if body else ""
    haystack = (title_text + " " + body_text).lower()

    for keywords, stype in _CONTENT_KEYWORDS:
        for kw in keywords:
            if kw in haystack:
                return stype

    nav = soup.find("nav")
    if nav:
        nav_text = nav.get_text().lower()
        if any(kw in nav_text for kw in ["forum", "topic", "thread", "board"]):
            return "forum"
        if any(kw in nav_text for kw in ["wiki", "page", "edit"]):
            return "wiki"

    return "website"


def extract_description(soup: BeautifulSoup) -> str:
    for meta in soup.find_all("meta"):
        if (meta.get("name") or "").lower() == "description":
            val = (meta.get("content") or "").strip()
            if val:
                return val[:300]
        if (meta.get("property") or "").lower() in ("og:description", "twitter:description"):
            val = (meta.get("content") or "").strip()
            if val:
                return val[:300]
    return ""


def extract_keywords(soup: BeautifulSoup) -> str:
    for meta in soup.find_all("meta"):
        if (meta.get("name") or "").lower() == "keywords":
            val = (meta.get("content") or "").strip()
            if val:
                return val[:500]
    return ""


def analyze_page(html: str, url: str) -> dict:
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        logger.warning("Failed to parse HTML for %s", url)
        return {}
    return {
        "language": detect_language(soup),
        "site_type": classify_site_type(soup, url),
        "description": extract_description(soup),
        "keywords": extract_keywords(soup),
    }
