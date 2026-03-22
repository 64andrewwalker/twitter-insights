import hmac
import os
import pytest


def test_verify_api_key_valid(monkeypatch):
    from server.auth import verify_api_key

    monkeypatch.setenv("TI_API_KEY", "a" * 32)
    monkeypatch.delenv("TI_API_KEY_OLD", raising=False)
    assert verify_api_key("a" * 32) is True


def test_verify_api_key_invalid(monkeypatch):
    from server.auth import verify_api_key

    monkeypatch.setenv("TI_API_KEY", "a" * 32)
    monkeypatch.delenv("TI_API_KEY_OLD", raising=False)
    assert verify_api_key("b" * 32) is False


def test_verify_api_key_old_accepted(monkeypatch):
    from server.auth import verify_api_key

    monkeypatch.setenv("TI_API_KEY", "new_key_" + "a" * 24)
    monkeypatch.setenv("TI_API_KEY_OLD", "old_key_" + "b" * 24)
    assert verify_api_key("old_key_" + "b" * 24) is True


def test_verify_api_key_empty_rejected(monkeypatch):
    from server.auth import verify_api_key

    monkeypatch.setenv("TI_API_KEY", "a" * 32)
    monkeypatch.delenv("TI_API_KEY_OLD", raising=False)
    assert verify_api_key("") is False


def test_validate_db_valid(tmp_path):
    import sqlite3
    from server.validate import validate_pushed_db
    from ti.db import init_db, rebuild_fts

    db_path = tmp_path / "valid.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    init_db(conn)
    conn.execute(
        "INSERT INTO users (user_id, screen_name, name) VALUES ('u1', 'test', 'Test')"
    )
    conn.execute(
        "INSERT INTO tweets (id, created_at, full_text, user_id) VALUES ('t1', '2026-01-01', 'hi', 'u1')"
    )
    rebuild_fts(conn)
    conn.close()

    errors = validate_pushed_db(db_path)
    assert errors == []


def test_validate_db_missing_table(tmp_path):
    import sqlite3
    from server.validate import validate_pushed_db

    db_path = tmp_path / "bad.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE tweets (id TEXT PRIMARY KEY)")
    conn.close()

    errors = validate_pushed_db(db_path)
    assert any("users" in e for e in errors)


def test_validate_db_corrupt(tmp_path):
    from server.validate import validate_pushed_db

    db_path = tmp_path / "corrupt.db"
    db_path.write_bytes(b"this is not sqlite")

    errors = validate_pushed_db(db_path)
    assert len(errors) > 0


# ── FastAPI endpoint tests ────────────────────────────────────


@pytest.fixture
def server_app(tmp_path, monkeypatch):
    """Create a FastAPI test client with a real DB."""
    import sqlite3

    from ti.db import init_db, rebuild_fts

    db_path = tmp_path / "ti.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    init_db(conn)
    conn.execute(
        "INSERT INTO users (user_id, screen_name, name) VALUES ('u1', 'alice', 'Alice')"
    )
    conn.execute(
        "INSERT INTO tweets (id, created_at, full_text, user_id, primary_tag, favorite_count, bookmark_count, views_count) "
        "VALUES ('t1', '2026-01-15', 'Claude Code is great', 'u1', 'claude-code-workflow', 10, 5, 1000)"
    )
    rebuild_fts(conn)
    conn.close()

    monkeypatch.setenv("TI_API_KEY", "a" * 32)
    monkeypatch.delenv("TI_API_KEY_OLD", raising=False)

    from server.app import create_app

    app = create_app(db_path=db_path)

    from fastapi.testclient import TestClient

    return TestClient(app)


def test_health(server_app):
    resp = server_app.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["db_ready"] is True


def test_search_requires_auth(server_app):
    resp = server_app.get("/v1/search", params={"q": "Claude"})
    assert resp.status_code == 401


def test_search_with_auth(server_app):
    resp = server_app.get(
        "/v1/search", params={"q": "Claude"}, headers={"X-API-Key": "a" * 32}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["command"] == "search"
    assert data["total"] >= 1


def test_stats_with_auth(server_app):
    resp = server_app.get("/v1/stats", headers={"X-API-Key": "a" * 32})
    assert resp.status_code == 200
    data = resp.json()
    assert data["command"] == "stats"
    assert data["total_tweets"] >= 1


def test_tags_with_auth(server_app):
    resp = server_app.get("/v1/tags", headers={"X-API-Key": "a" * 32})
    assert resp.status_code == 200
    data = resp.json()
    assert data["command"] == "tags"
    assert data["total"] > 0


def test_latest_with_auth(server_app):
    resp = server_app.get("/v1/latest", headers={"X-API-Key": "a" * 32})
    assert resp.status_code == 200
    assert resp.json()["command"] == "latest"


def test_show_with_auth(server_app):
    resp = server_app.get("/v1/show/t1", headers={"X-API-Key": "a" * 32})
    assert resp.status_code == 200
    assert resp.json()["results"][0]["id"] == "t1"


def test_show_not_found(server_app):
    resp = server_app.get("/v1/show/nonexistent", headers={"X-API-Key": "a" * 32})
    assert resp.status_code == 404


def test_cache_control_header(server_app):
    resp = server_app.get("/v1/stats", headers={"X-API-Key": "a" * 32})
    assert resp.headers.get("Cache-Control") == "no-store"


def test_validate_db_missing_columns(tmp_path):
    """Push rejects DB with missing columns on tweets."""
    import sqlite3
    from server.validate import validate_pushed_db

    db_path = tmp_path / "missing-cols.db"
    conn = sqlite3.connect(str(db_path))
    # Create tweets table missing primary_tag and other required columns
    conn.execute(
        "CREATE TABLE users (user_id TEXT PRIMARY KEY, screen_name TEXT, name TEXT)"
    )
    conn.execute(
        "CREATE TABLE tweets (id TEXT PRIMARY KEY, created_at TEXT, full_text TEXT)"
    )
    conn.execute("CREATE TABLE tags (id INTEGER PRIMARY KEY, name TEXT, category TEXT)")
    conn.execute("CREATE TABLE tweet_tags (tweet_id TEXT, tag_id INTEGER)")
    conn.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("CREATE TABLE import_log (id INTEGER PRIMARY KEY)")
    conn.close()

    errors = validate_pushed_db(db_path)
    assert any("Missing columns" in e for e in errors)


def test_validate_db_no_fts(tmp_path):
    """Push rejects DB where FTS5 table is missing."""
    import sqlite3
    from server.validate import validate_pushed_db
    from ti.db import SCHEMA_SQL

    db_path = tmp_path / "no-fts.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA_SQL)  # tables + indexes, but no FTS
    conn.close()

    errors = validate_pushed_db(db_path)
    assert any("FTS" in e for e in errors)


def test_validate_db_legacy_no_schema_version(tmp_path):
    """Push accepts legacy DB without schema_version in metadata."""
    import sqlite3
    from server.validate import validate_pushed_db
    from ti.db import init_db, rebuild_fts

    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    init_db(conn)
    conn.execute(
        "INSERT INTO users (user_id, screen_name, name) VALUES ('u1', 'test', 'Test')"
    )
    conn.execute(
        "INSERT INTO tweets (id, created_at, full_text, user_id) VALUES ('t1', '2026-01-01', 'hi', 'u1')"
    )
    rebuild_fts(conn)
    # No schema_version in metadata — should be accepted
    conn.close()

    errors = validate_pushed_db(db_path)
    assert errors == []


def test_validate_db_schema_version_too_new(tmp_path):
    """Push rejects DB with schema version newer than expected."""
    import sqlite3
    from server.validate import validate_pushed_db
    from ti.db import init_db, rebuild_fts

    db_path = tmp_path / "new-schema.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    init_db(conn)
    conn.execute(
        "INSERT INTO users (user_id, screen_name, name) VALUES ('u1', 'test', 'Test')"
    )
    conn.execute(
        "INSERT INTO tweets (id, created_at, full_text, user_id) VALUES ('t1', '2026-01-01', 'hi', 'u1')"
    )
    rebuild_fts(conn)
    conn.execute(
        "INSERT OR REPLACE INTO metadata (key, value) VALUES ('schema_version', '99')"
    )
    conn.commit()
    conn.close()

    errors = validate_pushed_db(db_path)
    assert any("Upgrade server" in e for e in errors)


def test_server_503_no_db(tmp_path, monkeypatch):
    """Queries return 503 when DB is not initialized."""
    monkeypatch.setenv("TI_API_KEY", "a" * 32)
    monkeypatch.delenv("TI_API_KEY_OLD", raising=False)

    no_db_path = tmp_path / "nonexistent.db"  # file does not exist
    from server.app import create_app

    app = create_app(db_path=no_db_path)

    from fastapi.testclient import TestClient

    client = TestClient(app)

    # Health should work but show db_ready: false
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["db_ready"] is False

    # Query endpoints should return 503
    resp = client.get("/v1/stats", headers={"X-API-Key": "a" * 32})
    assert resp.status_code == 503


def test_server_api_key_too_short(tmp_path, monkeypatch):
    """Server rejects API keys shorter than 32 chars at startup."""
    monkeypatch.setenv("TI_API_KEY", "short")
    monkeypatch.delenv("TI_API_KEY_OLD", raising=False)

    from server.app import create_app

    with pytest.raises(RuntimeError, match="at least 32 characters"):
        create_app(db_path=tmp_path / "test.db")


def test_server_tag_endpoint(server_app):
    """GET /v1/tag/{name} returns filtered tweets."""
    resp = server_app.get(
        "/v1/tag/claude-code-workflow", headers={"X-API-Key": "a" * 32}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["command"] == "tag"


def test_server_author_endpoint(server_app):
    """GET /v1/author/{handle} returns filtered tweets."""
    resp = server_app.get("/v1/author/alice", headers={"X-API-Key": "a" * 32})
    assert resp.status_code == 200
    data = resp.json()
    assert data["command"] == "author"
    assert data["total"] >= 1
