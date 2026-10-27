"""
Offline unit tests for Abyssal: no running services or i2pd needed.
Run with: abyssal/.venv/bin/python -m pytest tests/abyssal/test_unit.py
"""
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "abyssal"))

from abyssal.api.router import _normalize_seed_url  # noqa: E402
from abyssal.db.search import _clean_snippet, _host_sql, fts_query  # noqa: E402
from abyssal.wayback import storage  # noqa: E402
from abyssal.wayback.rewrite import rewrite_external_urls  # noqa: E402
from abyssal.config import API_KEY, PROXY_TOKEN  # noqa: E402


class TestFtsQuery:
    def test_terms_are_quoted(self):
        assert fts_query("stats.i2p tunnel") == '"stats.i2p" "tunnel"'

    def test_quotes_are_escaped(self):
        assert fts_query('say "hi') == '"say" """hi"'

    def test_prefix_kept(self):
        assert fts_query("tunn*") == '"tunn"*'

    def test_empty_and_junk(self):
        assert fts_query("") == ""
        assert fts_query('  "" * ') == ""

    def test_queries_are_valid_fts5(self):
        db = sqlite3.connect(":memory:")
        db.execute("CREATE VIRTUAL TABLE t USING fts5(body, tokenize='porter unicode61')")
        db.execute("INSERT INTO t VALUES ('tunnel build stats on stats.i2p')")
        for q in ['"', "foo AND", "c++", "stats.i2p", "a-b", "x:y", "NOT", "(", "tunn*"]:
            match = fts_query(q)
            if match:
                db.execute("SELECT * FROM t WHERE t MATCH ?", (match,)).fetchall()
        assert db.execute("SELECT count(*) FROM t WHERE t MATCH ?", (fts_query("stats.i2p"),)).fetchone()[0] == 1


class TestSnippet:
    def test_markup_is_removed(self):
        out = _clean_snippet('a <img src=x onerror=alert(1)> \x02b\x03 <scr')
        assert "<img" not in out and "onerror" not in out and "<scr" not in out
        assert "<b>b</b>" in out

    def test_partial_leading_tag_removed(self):
        assert _clean_snippet('ipt>alert(1)</script> x') == "alert(1) x"

    def test_entities_not_double_escaped(self):
        assert _clean_snippet("fish &amp; chips") == "fish &amp; chips"


class TestHostSql:
    def test_extracts_host(self):
        db = sqlite3.connect(":memory:")
        db.execute("CREATE TABLE p (url TEXT)")
        urls = ["http://notbob.i2p/", "http://notbob.i2p", "http://notbob.i2p/a/b", "https://bob.i2p/x"]
        db.executemany("INSERT INTO p VALUES (?)", [(u,) for u in urls])
        hosts = [r[0] for r in db.execute(f"SELECT {_host_sql()} FROM p")]
        assert hosts == ["notbob.i2p", "notbob.i2p", "notbob.i2p", "bob.i2p"]


class TestSeedUrl:
    def test_bare_host(self):
        assert _normalize_seed_url("identiguy") == "http://identiguy.i2p"

    def test_keeps_path(self):
        assert _normalize_seed_url("https://stats.i2p/netdb") == "http://stats.i2p/netdb"


class TestStorage:
    def test_captured_at_sets_name_and_time(self, tmp_path, monkeypatch):
        monkeypatch.setattr(storage, "ARCHIVE_ROOT", tmp_path)
        when = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        meta = storage.store_snapshot("http://zzz.i2p/", "<p>x</p>", 200, captured_at=when)
        assert Path(meta["file_path"]).name.startswith("20260102_030405_200_")
        assert meta["snapshot_time"] == when.isoformat()
        assert storage.load_snapshot(meta["file_path"]) == "<p>x</p>"


class TestRewrite:
    def test_api_key_never_embedded(self):
        out = rewrite_external_urls('<img src="/a.png"><link href="s.css">', "http://x.i2p/")
        assert API_KEY not in out
        assert f"token={PROXY_TOKEN}" in out
