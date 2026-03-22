import sqlite3
import pytest
from pathlib import Path


def test_create_snapshot_produces_valid_db(tmp_path):
    from ti.push import create_snapshot
    from ti.db import get_connection, init_db

    db_path = tmp_path / "source.db"
    conn = get_connection(db_path)
    init_db(conn)
    conn.execute(
        "INSERT INTO users (user_id, screen_name, name) VALUES ('u1', 'alice', 'Alice')"
    )
    conn.execute(
        "INSERT INTO tweets (id, created_at, full_text, user_id) VALUES ('t1', '2026-01-01', 'hello world', 'u1')"
    )
    conn.commit()
    conn.close()

    snapshot = create_snapshot(db_path)
    assert snapshot != db_path
    assert snapshot.exists()
    assert not Path(str(snapshot) + "-wal").exists()
    assert not Path(str(snapshot) + "-shm").exists()

    snap_conn = sqlite3.connect(str(snapshot))
    count = snap_conn.execute("SELECT COUNT(*) FROM tweets").fetchone()[0]
    snap_conn.close()
    assert count == 1
    snapshot.unlink()


def test_create_snapshot_includes_wal_data(tmp_path):
    from ti.push import create_snapshot
    from ti.db import get_connection, init_db

    db_path = tmp_path / "wal-test.db"
    conn = get_connection(db_path)
    init_db(conn)
    conn.execute(
        "INSERT INTO users (user_id, screen_name, name) VALUES ('u1', 'bob', 'Bob')"
    )
    conn.execute(
        "INSERT INTO tweets (id, created_at, full_text, user_id) VALUES ('t1', '2026-01-01', 'wal data', 'u1')"
    )
    conn.commit()

    snapshot = create_snapshot(db_path)
    snap_conn = sqlite3.connect(str(snapshot))
    text = snap_conn.execute("SELECT full_text FROM tweets WHERE id='t1'").fetchone()[0]
    snap_conn.close()
    assert text == "wal data"
    conn.close()
    snapshot.unlink()


def test_create_snapshot_unique_filenames(tmp_path):
    from ti.push import create_snapshot
    from ti.db import get_connection, init_db

    db_path = tmp_path / "multi.db"
    conn = get_connection(db_path)
    init_db(conn)
    conn.close()

    s1 = create_snapshot(db_path)
    s2 = create_snapshot(db_path)
    assert s1 != s2
    s1.unlink()
    s2.unlink()


def test_upload_db_sends_correct_headers(tmp_path):
    """upload_db sends API key, force header, and version header."""
    from unittest.mock import patch, MagicMock
    from ti.push import upload_db

    db_path = tmp_path / "test.db"
    db_path.write_bytes(b"fake db content")

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"version": "v1", "tweet_count": 0}
    mock_resp.raise_for_status.return_value = None

    with patch("ti.push.requests.Session") as MockSession:
        mock_session = MagicMock()
        mock_session.post.return_value = mock_resp
        MockSession.return_value = mock_session
        upload_db(
            db_path,
            "https://example.com",
            "my-key",
            force=True,
            last_version="2026-01-01",
        )
        mock_session.post.assert_called_once()
        call_kwargs = mock_session.post.call_args[1]
        headers = call_kwargs["headers"]
        assert headers["X-API-Key"] == "my-key"
        assert headers["X-TI-Force-Push"] == "true"
        assert headers["X-TI-DB-Version"] == "2026-01-01"


def test_push_db_retries_on_failure(tmp_path):
    """push_db retries and cleans up snapshot."""
    from unittest.mock import patch, MagicMock
    from ti.push import push_db, create_snapshot
    from ti.db import get_connection, init_db
    import requests as req

    db_path = tmp_path / "retry.db"
    conn = get_connection(db_path)
    init_db(conn)
    conn.close()

    call_count = 0

    def mock_upload(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise req.ConnectionError("network error")
        return {"version": "ok", "tweet_count": 0}

    with patch("ti.push.upload_db", side_effect=mock_upload):
        with patch("time.sleep"):  # skip actual sleep
            result = push_db(db_path, "https://x.com", "key", retries=3)
            assert result["version"] == "ok"
            assert call_count == 3

    # Verify snapshot was cleaned up
    import glob

    snapshots = glob.glob(str(tmp_path / "ti-snapshot-*.db"))
    assert len(snapshots) == 0
