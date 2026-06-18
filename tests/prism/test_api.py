"""
Prism API integration tests.

Tests the Prism router, browser, and addressbook services.
Run with: cd prism && python -m pytest ../tests/prism/ -v

Requires:
  - Prism services running (router on 8001, browser on 8002, addressbook on 8005)
  - Or set PRISM_ROUTER_URL, PRISM_BROWSER_URL, PRISM_ADDRESSBOOK_URL env vars
"""
import os
import httpx
import pytest

def _get_url(env_var, host_port, docker_name):
    url = os.getenv(env_var, f"http://localhost:{host_port}")
    try:
        httpx.get(f"{url}/health", timeout=2)
        return url
    except Exception:
        docker_url = f"http://{docker_name}:8001" if "router" in env_var else f"http://{docker_name}:{host_port}"
        try:
            httpx.get(f"{docker_url}/health", timeout=2)
            return docker_url
        except Exception:
            return url

ROUTER_URL = _get_url("PRISM_ROUTER_URL", 8001, "prism-router")
BROWSER_URL = os.getenv("PRISM_BROWSER_URL", "http://localhost:8002")
ADDRESSBOOK_URL = os.getenv("PRISM_ADDRESSBOOK_URL", "http://localhost:8005")
API_KEY = "dev-key-12345"


# --- Router Service ---

class TestRouterHealth:
    def test_health(self):
        r = httpx.get(f"{ROUTER_URL}/health")
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "ok"

class TestRouterStatus:
    def test_status_requires_auth(self):
        r = httpx.get(f"{ROUTER_URL}/api/status")
        assert r.status_code in (401, 403)

    def test_status_with_auth(self):
        r = httpx.get(f"{ROUTER_URL}/api/status", headers={"x-api-key": API_KEY})
        assert r.status_code in (200, 503)

    def test_status_response_shape(self):
        r = httpx.get(f"{ROUTER_URL}/api/status", headers={"x-api-key": API_KEY})
        if r.status_code == 503:
            pytest.skip("i2pd not reachable")
        d = r.json()
        assert "uptime" in d
        assert "active_peers" in d
        assert "tunnel_count" in d
        assert "status" in d

class TestRouterBandwidth:
    def test_bandwidth_requires_auth(self):
        r = httpx.get(f"{ROUTER_URL}/api/bandwidth")
        assert r.status_code in (401, 403)

    def test_bandwidth_response_shape(self):
        r = httpx.get(f"{ROUTER_URL}/api/bandwidth", headers={"x-api-key": API_KEY})
        if r.status_code == 503:
            pytest.skip("i2pd not reachable")
        d = r.json()
        assert "inbound_rate" in d
        assert "outbound_rate" in d

class TestRouterTunnels:
    def test_tunnels_requires_auth(self):
        r = httpx.get(f"{ROUTER_URL}/api/tunnels")
        assert r.status_code in (401, 403)

class TestRouterInfo:
    def test_router_info_requires_auth(self):
        r = httpx.get(f"{ROUTER_URL}/api/router-info")
        assert r.status_code in (401, 403)

class TestRouterDetails:
    def test_router_details_requires_auth(self):
        r = httpx.get(f"{ROUTER_URL}/api/router-details")
        assert r.status_code in (401, 403)

class TestRouterHealthScore:
    def test_router_health_requires_auth(self):
        r = httpx.get(f"{ROUTER_URL}/api/router-health")
        assert r.status_code in (401, 403)

    def test_router_health_response_shape(self):
        r = httpx.get(f"{ROUTER_URL}/api/router-health", headers={"x-api-key": API_KEY})
        if r.status_code == 503:
            pytest.skip("i2pd not reachable")
        d = r.json()
        assert "health_score" in d
        assert "tunnels" in d
        assert "bandwidth" in d
        assert "network" in d
        assert "flags" in d

class TestRouterCommands:
    def test_commands_requires_auth(self):
        r = httpx.get(f"{ROUTER_URL}/api/commands")
        assert r.status_code in (401, 403)

class TestRouterTransports:
    def test_transports_requires_auth(self):
        r = httpx.get(f"{ROUTER_URL}/api/transports")
        assert r.status_code in (401, 403)

class TestRouterDestinations:
    def test_destinations_requires_auth(self):
        r = httpx.get(f"{ROUTER_URL}/api/local-destinations")
        assert r.status_code in (401, 403)

class TestRouterConfig:
    def test_config_requires_auth(self):
        r = httpx.get(f"{ROUTER_URL}/api/config")
        assert r.status_code in (401, 403)

    def test_config_response(self):
        r = httpx.get(f"{ROUTER_URL}/api/config", headers={"x-api-key": API_KEY})
        assert r.status_code == 200
        d = r.json()
        assert "poll_interval" in d
        assert "api_version" in d

class TestBandwidthSet:
    def test_set_bandwidth_requires_auth(self):
        r = httpx.post(f"{ROUTER_URL}/api/bandwidth/set", json={"inbound": 64})
        assert r.status_code in (401, 403)

class TestRunCommand:
    def test_run_command_requires_auth(self):
        r = httpx.post(f"{ROUTER_URL}/api/command/test")
        assert r.status_code in (401, 403)


# --- Browser Service ---

class TestBrowserProxy:
    def test_proxy_requires_auth(self):
        r = httpx.get(f"{BROWSER_URL}/api/browser/proxy", params={"url": "http://test.i2p"})
        assert r.status_code == 403

    def test_proxy_with_query_key(self):
        r = httpx.get(
            f"{BROWSER_URL}/api/browser/proxy",
            params={"url": "http://test.i2p", "api_key": API_KEY},
        )
        assert r.status_code != 403

    def test_proxy_with_header_key(self):
        r = httpx.get(
            f"{BROWSER_URL}/api/browser/proxy",
            params={"url": "http://test.i2p"},
            headers={"x-api-key": API_KEY},
        )
        assert r.status_code != 403

    def test_proxy_invalid_url(self):
        r = httpx.get(
            f"{BROWSER_URL}/api/browser/proxy",
            params={"url": ""},
            headers={"x-api-key": API_KEY},
        )
        assert r.status_code in (400, 502, 504)

class TestBrowserBookmarks:
    def test_bookmarks_requires_auth(self):
        r = httpx.get(f"{BROWSER_URL}/api/browser/bookmarks")
        assert r.status_code == 403

    def test_bookmarks_with_auth(self):
        r = httpx.get(f"{BROWSER_URL}/api/browser/bookmarks", headers={"x-api-key": API_KEY})
        assert r.status_code == 200
        d = r.json()
        assert "bookmarks" in d

    def test_add_bookmark_requires_auth(self):
        r = httpx.post(f"{BROWSER_URL}/api/browser/bookmarks", json=[{"name": "test", "url": "http://test.i2p"}])
        assert r.status_code == 403


# --- Addressbook Service ---

class TestAddressbookSubscriptions:
    def test_subscriptions_requires_auth(self):
        r = httpx.get(f"{ADDRESSBOOK_URL}/api/addressbook/subscriptions")
        assert r.status_code == 403

    def test_subscriptions_with_auth(self):
        r = httpx.get(f"{ADDRESSBOOK_URL}/api/addressbook/subscriptions", headers={"x-api-key": API_KEY})
        assert r.status_code == 200
        d = r.json()
        assert "subscriptions" in d
        assert "total_entries" in d

    def test_add_subscription_requires_auth(self):
        r = httpx.post(
            f"{ADDRESSBOOK_URL}/api/addressbook/subscriptions",
            json={"url": "http://test.i2p/hosts.txt"},
        )
        assert r.status_code == 403

    def test_remove_subscription_requires_auth(self):
        r = httpx.delete(
            f"{ADDRESSBOOK_URL}/api/addressbook/subscriptions",
            params={"url": "http://test.i2p/hosts.txt"},
        )
        assert r.status_code == 403


# --- Error Handling ---

class TestErrorHandling:
    def test_invalid_api_key(self):
        r = httpx.get(f"{ROUTER_URL}/api/status", headers={"x-api-key": "wrong-key"})
        assert r.status_code == 403

    def test_missing_api_key(self):
        r = httpx.get(f"{ROUTER_URL}/api/status")
        assert r.status_code in (401, 403)

    def test_nonexistent_endpoint(self):
        r = httpx.get(f"{ROUTER_URL}/api/nonexistent")
        assert r.status_code == 404
