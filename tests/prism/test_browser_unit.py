"""
Offline unit tests for the Prism browser proxy auth: no running services or i2pd needed.
Run with: abyssal/.venv/bin/python -m pytest tests/prism/test_browser_unit.py
"""
import importlib.util
import sys
from pathlib import Path

from fastapi.testclient import TestClient

SERVICES = Path(__file__).resolve().parents[2] / "prism" / "backend" / "services"
sys.path.insert(0, str(SERVICES / "router"))

_spec = importlib.util.spec_from_file_location("prism_browser_main", SERVICES / "browser" / "main.py")
browser = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(browser)

client = TestClient(browser.app)
PROXY = "/api/browser/proxy"


def test_token_endpoint_needs_key():
    assert client.get("/api/browser/token").status_code == 403
    r = client.get("/api/browser/token", headers={"x-api-key": browser.API_KEY})
    assert r.status_code == 200
    assert r.json()["token"] == browser.BROWSER_TOKEN
    assert browser.BROWSER_TOKEN != browser.API_KEY


def test_proxy_rejects_bad_token():
    r = client.get(PROXY, params={"url": "http://x.i2p", "token": "nope"})
    assert r.status_code == 403


def test_public_token_is_i2p_only():
    r = client.get(PROXY, params={"url": "http://example.com", "token": browser.PROXY_TOKEN})
    assert r.status_code == 403


def test_non_http_scheme_rejected():
    r = client.get(PROXY, params={"url": "file:///etc/passwd", "token": browser.BROWSER_TOKEN})
    assert r.status_code == 400


def test_rewritten_links_use_token_not_key():
    html = browser._rewrite_html('<a href="/b">b</a><img src="c.png">', "http://x.i2p/", browser.BROWSER_TOKEN)
    assert browser.API_KEY not in html
    assert f"token={browser.BROWSER_TOKEN}" in html


def test_proxied_html_is_sandboxed():
    assert "sandbox" in browser.PROXIED_HTML_HEADERS["Content-Security-Policy"]
    assert "allow-same-origin" not in browser.PROXIED_HTML_HEADERS["Content-Security-Policy"]
