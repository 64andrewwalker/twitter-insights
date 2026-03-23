"""Database connection management and read-write lock for the server."""

import sqlite3
import threading
from pathlib import Path

DB_PATH = Path("/data/ti.db")


class DBManager:
    """Connection manager with read-write lock for atomic DB swaps."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or DB_PATH
        self._lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        self.last_push_at: str | None = None

    @property
    def db_ready(self) -> bool:
        return self.db_path.exists()

    def get_connection(self) -> sqlite3.Connection:
        """Get a read-only connection. Thread-safe via _lock."""
        if not self.db_ready:
            raise FileNotFoundError("Database not initialized")
        with self._lock:
            if self._conn is None or not self._is_alive(self._conn):
                self._conn = self._open()
            return self._conn

    def _open(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _is_alive(self, conn: sqlite3.Connection) -> bool:
        try:
            conn.execute("SELECT 1")
            return True
        except Exception:
            return False

    def swap_db(self) -> None:
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
        self._conn = None

    @property
    def write_lock(self) -> threading.Lock:
        return self._write_lock
