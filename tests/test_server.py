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
