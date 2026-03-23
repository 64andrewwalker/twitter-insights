"""End-to-end tests against the live Railway deployment.

Run with: TI_E2E_URL=https://ti-api-production.up.railway.app TI_E2E_KEY=<key> pytest tests/test_e2e_server.py -v
Skipped if TI_E2E_URL is not set.
"""

import os

import pytest
import requests

E2E_URL = os.environ.get("TI_E2E_URL", "")
E2E_KEY = os.environ.get("TI_E2E_KEY", "")

pytestmark = pytest.mark.skipif(not E2E_URL, reason="TI_E2E_URL not set")

# Bypass any system proxy for direct E2E testing
_session = requests.Session()
_session.trust_env = False  # Ignore system proxy settings


def _get(path, params=None, auth=True):
    headers = {"X-API-Key": E2E_KEY} if auth else {}
    resp = _session.get(f"{E2E_URL}{path}", params=params, headers=headers, timeout=15)
    return resp


def test_health_unauthenticated():
    # Health endpoint works without auth; retry once on transient proxy/network issues
    import time

    for attempt in range(2):
        try:
            resp = _get("/health", auth=False)
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert data["db_ready"] is True
            return
        except Exception:
            if attempt == 0:
                time.sleep(2)
            else:
                raise


def test_health_has_no_cache():
    resp = _get("/health", auth=False)
    assert resp.headers.get("Cache-Control") == "no-store"


def test_stats():
    resp = _get("/v1/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["command"] == "stats"
    assert data["total_tweets"] > 0
    assert data["classified"] > 0
    assert data["authors"] > 0
    assert "date_range" in data
    assert data["date_range"]["from"] != ""
    assert "last_push_at" in data
    assert "db_version" in data


def test_search():
    resp = _get("/v1/search", {"q": "Claude", "limit": 5})
    assert resp.status_code == 200
    data = resp.json()
    assert data["command"] == "search"
    assert data["total"] > 0
    assert data["returned"] <= 5
    assert len(data["results"]) == data["returned"]
    # Verify result structure
    r = data["results"][0]
    assert "id" in r
    assert "author" in r
    assert "text" in r
    assert "engagement" in r


def test_search_sort_validation():
    resp = _get("/v1/search", {"q": "test", "sort": "invalid"})
    assert resp.status_code == 400


def test_tags():
    resp = _get("/v1/tags")
    assert resp.status_code == 200
    data = resp.json()
    assert data["command"] == "tags"
    assert data["total"] == 32
    assert len(data["results"]) == 32
    # Each tag has name, category, count
    for tag in data["results"]:
        assert "name" in tag
        assert "category" in tag
        assert "count" in tag


def test_latest():
    resp = _get("/v1/latest", {"n": 3})
    assert resp.status_code == 200
    data = resp.json()
    assert data["command"] == "latest"
    assert data["returned"] == 3


def test_show_existing():
    # First get a valid ID from latest
    latest = _get("/v1/latest", {"n": 1}).json()
    tweet_id = latest["results"][0]["id"]

    resp = _get(f"/v1/show/{tweet_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["results"][0]["id"] == tweet_id


def test_show_not_found():
    resp = _get("/v1/show/nonexistent_id_12345")
    assert resp.status_code == 404


def test_tag_filter():
    resp = _get("/v1/tag/claude-code-workflow", {"limit": 3})
    assert resp.status_code == 200
    data = resp.json()
    assert data["command"] == "tag"
    assert data["total"] > 0


def test_author_filter():
    # Get an author from latest
    latest = _get("/v1/latest", {"n": 1}).json()
    author = latest["results"][0]["author"].lstrip("@")

    resp = _get(f"/v1/author/{author}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["command"] == "author"
    assert data["total"] > 0


def test_auth_required():
    resp = _get("/v1/stats", auth=False)
    assert resp.status_code == 401


def test_auth_invalid_key():
    headers = {"X-API-Key": "invalid" * 10}
    resp = _session.get(f"{E2E_URL}/v1/stats", headers=headers, timeout=15)
    assert resp.status_code == 401


def test_cache_control_on_all_responses():
    for path, params in [
        ("/v1/stats", None),
        ("/v1/tags", None),
        ("/v1/search", {"q": "test"}),
    ]:
        resp = _get(path, params)
        assert (
            resp.headers.get("Cache-Control") == "no-store"
        ), f"Missing Cache-Control on {path}"
