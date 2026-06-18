"""
Abyssal API integration tests.

Tests the full API stack: search, directory, wayback, addressbook, crawler admin.
Run with: cd abyssal && python -m pytest ../tests/abyssal/ -v

Requires:
  - Backend running on localhost:8000 (or set ABYSSAL_URL env var)
  - i2pd running for I2P-dependent endpoints
"""
import os
import httpx
import pytest

# Try host-mapped port first, then Docker network name
def _get_abyssal_url():
    # Check if host port 80 is reachable (nginx proxy)
    host_url = os.getenv("ABYSSAL_URL", "http://localhost")
    try:
        httpx.get(f"{host_url}/api/abyssal/sites?page=1&per_page=1", timeout=2)
        return host_url
    except Exception:
        pass
    # Fall back to Docker network name
    docker_url = "http://abyssal-backend:8000"
    try:
        httpx.get(f"{docker_url}/api/abyssal/sites?page=1&per_page=1", timeout=2)
        return docker_url
    except Exception:
        pass
    # Default to host URL for error messages
    return host_url

BASE_URL = _get_abyssal_url()
API = f"{BASE_URL}/api/abyssal"
API_KEY = os.getenv("API_KEY", "dev-key-12345")


@pytest.fixture
def client():
    return httpx.AsyncClient(base_url=API, timeout=30.0)


@pytest.fixture
def admin_client():
    return httpx.AsyncClient(
        base_url=API, timeout=30.0, headers={"api-key": API_KEY}
    )


# ── Health & Basic ─────────────────────────────────────────────────────────

class TestHealth:
    def test_search_empty_query(self):
        """Empty search returns empty results."""
        r = httpx.get(f"{API}/search?q=")
        assert r.status_code == 200
        d = r.json()
        assert d["results"] == []
        assert d["total"] == 0

    def test_search_no_results(self):
        """Search for gibberish returns no results."""
        r = httpx.get(f"{API}/search?q=xyznonexistent12345")
        assert r.status_code == 200
        d = r.json()
        assert d["results"] == []
        assert d["total"] == 0

    def test_facets(self):
        """Facets endpoint returns language and site_type lists."""
        r = httpx.get(f"{API}/facets")
        assert r.status_code == 200
        d = r.json()
        assert "languages" in d
        assert "site_types" in d
        assert isinstance(d["languages"], list)
        assert isinstance(d["site_types"], list)


# ── Directory ──────────────────────────────────────────────────────────────

class TestDirectory:
    def test_sites_pagination(self):
        """Sites endpoint returns paginated results."""
        r = httpx.get(f"{API}/sites", params={"page": 1, "per_page": 5})
        assert r.status_code == 200
        d = r.json()
        assert "results" in d
        assert "total" in d
        assert "page" in d
        assert "per_page" in d
        assert d["page"] == 1
        assert d["per_page"] == 5

    def test_sites_filter_language(self):
        """Sites can be filtered by language."""
        r = httpx.get(f"{API}/sites", params={"language": "en", "per_page": 5})
        assert r.status_code == 200
        d = r.json()
        for site in d.get("results", []):
            assert site.get("language") == "en"

    def test_sites_filter_site_type(self):
        """Sites can be filtered by site type."""
        r = httpx.get(f"{API}/sites", params={"site_type": "forum", "per_page": 5})
        assert r.status_code == 200
        d = r.json()
        for site in d.get("results", []):
            assert site.get("site_type") == "forum"

    def test_site_status_pagination(self):
        """Site status endpoint returns paginated results."""
        r = httpx.get(f"{API}/site-status", params={"page": 1, "per_page": 10})
        assert r.status_code == 200
        d = r.json()
        assert "sites" in d
        assert "total" in d
        assert d["page"] == 1

    def test_site_detail_404(self):
        """Requesting a nonexistent site returns 404."""
        r = httpx.get(f"{API}/sites/thisdoesnotexist.i2p")
        assert r.status_code == 404

    def test_graph(self):
        """Graph endpoint returns nodes and links."""
        r = httpx.get(f"{API}/graph")
        assert r.status_code == 200
        d = r.json()
        assert "nodes" in d
        assert "links" in d


# ── Wayback ────────────────────────────────────────────────────────────────

class TestWayback:
    def test_stats(self):
        """Wayback stats returns snapshot/url counts."""
        r = httpx.get(f"{API}/wayback/stats")
        assert r.status_code == 200
        d = r.json()
        assert "total_snapshots" in d
        assert "total_urls" in d
        assert "total_size_bytes" in d

    def test_urls_pagination(self):
        """Wayback URLs endpoint returns paginated results."""
        r = httpx.get(f"{API}/wayback/urls", params={"limit": 10, "offset": 0})
        assert r.status_code == 200
        d = r.json()
        assert "urls" in d
        assert "total" in d
        assert d["limit"] == 10

    def test_snapshots_empty_url(self):
        """Snapshots with empty URL returns empty list."""
        r = httpx.get(f"{API}/wayback/snapshots", params={"url": ""})
        assert r.status_code == 200
        d = r.json()
        assert d["snapshots"] == []
        assert d["total"] == 0

    def test_snapshot_404(self):
        """Requesting a nonexistent snapshot returns 404."""
        r = httpx.get(f"{API}/wayback/snapshots/999999")
        assert r.status_code == 404


# ── Address Book ───────────────────────────────────────────────────────────

class TestAddressBook:
    def test_addressbook_pagination(self):
        """Address book returns paginated results."""
        r = httpx.get(f"{API}/addressbook", params={"page": 1, "per_page": 10})
        assert r.status_code == 200
        d = r.json()
        assert "sites" in d
        assert "total" in d
        assert d["page"] == 1

    def test_addressbook_filter(self):
        """Address book supports text filter."""
        r = httpx.get(f"{API}/addressbook", params={"q": "i2p", "per_page": 5})
        assert r.status_code == 200
        d = r.json()
        for site in d.get("sites", []):
            assert "i2p" in site["hostname"].lower()

    def test_hosts_txt(self):
        """hosts.txt export returns text/plain."""
        r = httpx.get(f"{API}/addressbook/hosts.txt")
        assert r.status_code == 200
        assert "text/plain" in r.headers.get("content-type", "")

    def test_hosts_txt_active_filter(self):
        """hosts.txt active filter returns only online hosts."""
        r = httpx.get(f"{API}/addressbook/hosts.txt", params={"filter": "active"})
        assert r.status_code == 200


# ── Crawler Admin (auth required) ──────────────────────────────────────────

class TestCrawlerAdmin:
    def test_list_jobs_requires_auth(self):
        """Crawler jobs endpoint requires API key."""
        r = httpx.get(f"{API}/crawl/jobs")
        assert r.status_code == 403

    def test_list_jobs_with_auth(self):
        """Crawler jobs returns paginated results with valid key."""
        r = httpx.get(f"{API}/crawl/jobs", headers={"api-key": API_KEY})
        assert r.status_code == 200
        d = r.json()
        assert "jobs" in d
        assert "total" in d

    def test_list_jobs_pagination(self):
        """Crawler jobs pagination works."""
        r = httpx.get(
            f"{API}/crawl/jobs",
            headers={"api-key": API_KEY},
            params={"page": 1, "per_page": 5},
        )
        assert r.status_code == 200
        d = r.json()
        assert d["page"] == 1
        assert d["per_page"] == 5

    def test_start_crawl_requires_auth(self):
        """Starting a crawl requires API key."""
        r = httpx.post(f"{API}/crawl/start", json={"url": "http://test.i2p"})
        assert r.status_code == 403

    def test_start_crawl_invalid_url(self):
        """Starting a crawl with empty URL returns 400."""
        r = httpx.post(
            f"{API}/crawl/start",
            json={"url": ""},
            headers={"api-key": API_KEY},
        )
        assert r.status_code == 400

    def test_delete_job_requires_auth(self):
        """Deleting a job requires API key."""
        r = httpx.delete(f"{API}/crawl/jobs/999999")
        assert r.status_code == 403

    def test_pause_resume_requires_auth(self):
        """Pause/resume endpoints require API key."""
        r = httpx.post(f"{API}/crawl/jobs/999999/pause")
        assert r.status_code == 403
        r = httpx.post(f"{API}/crawl/jobs/999999/resume")
        assert r.status_code == 403


# ── Page Viewer ────────────────────────────────────────────────────────────

class TestPageViewer:
    def test_page_404(self):
        """Requesting a nonexistent page returns 404."""
        r = httpx.get(f"{API}/pages/999999")
        assert r.status_code == 404

    def test_page_view_404(self):
        """Requesting a nonexistent page view returns 404."""
        r = httpx.get(f"{API}/pages/999999/view")
        assert r.status_code == 404


# ── Eepsite ────────────────────────────────────────────────────────────────

class TestEepsite:
    def test_eepsite_endpoint(self):
        """Eepsite endpoint returns tunnel info or empty list."""
        r = httpx.get(f"{API}/eepsite")
        assert r.status_code == 200
        d = r.json()
        assert "tunnels" in d
