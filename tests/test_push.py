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
