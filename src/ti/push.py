"""Database snapshot, upload, and auto-push."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import requests


def create_snapshot(db_path: Path) -> Path:
    """Create a self-contained snapshot via VACUUM INTO. No WAL/SHM deps."""
    snapshot_path = db_path.parent / f"ti-snapshot-{uuid4().hex[:8]}.db"
    assert "'" not in str(snapshot_path), "snapshot path must not contain single quotes"
    conn = sqlite3.connect(str(db_path))
    conn.execute(f"VACUUM INTO '{snapshot_path}'")
    conn.close()
    return snapshot_path


def upload_db(
    snapshot_path: Path,
    api_url: str,
    api_key: str,
    force: bool = False,
    last_version: str | None = None,
    timeout: int = 30,
) -> dict:
    """Upload a snapshot to the server. Returns server response dict."""
    url = f"{api_url.rstrip('/')}/v1/db/push"
    headers = {"X-API-Key": api_key}
    if force:
        headers["X-TI-Force-Push"] = "true"
    if last_version:
        headers["X-TI-DB-Version"] = last_version

    session = requests.Session()
    with open(snapshot_path, "rb") as f:
        resp = session.post(
            url,
            files={"file": ("ti.db", f, "application/octet-stream")},
            headers=headers,
            timeout=timeout,
        )
    resp.raise_for_status()
    return resp.json()


def push_db(
    db_path: Path, api_url: str, api_key: str, force: bool = False, retries: int = 3
) -> dict:
    """Full push flow: snapshot -> upload -> cleanup. With retries for manual push."""
    snapshot = create_snapshot(db_path)
    try:
        last_err = None
        for attempt in range(retries):
            try:
                result = upload_db(snapshot, api_url, api_key, force=force)
                return result
            except (requests.RequestException, OSError) as e:
                last_err = e
                if attempt < retries - 1:
                    import time

                    time.sleep(2**attempt)
        assert last_err is not None, "push_db: no attempts made"
        raise last_err
    finally:
        snapshot.unlink(missing_ok=True)


def auto_push(api_url: str, api_key: str, db_path: Path) -> None:
    """Fire-and-forget push via detached subprocess."""
    if not api_url or not api_key:
        return
    subprocess.Popen(
        [sys.executable, "-m", "ti.push", str(db_path), api_url],
        env={**os.environ, "TI_PUSH_API_KEY": api_key},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


if __name__ == "__main__":
    import logging

    if len(sys.argv) < 3:
        sys.exit(1)

    _db_path = Path(sys.argv[1])
    _api_url = sys.argv[2]
    _api_key = os.environ.get("TI_PUSH_API_KEY", "")

    if not _api_key:
        sys.exit(1)

    log_dir = (
        Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "ti"
    )
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(log_dir / "push.log"),
        level=logging.INFO,
        format="%(asctime)s %(message)s",
    )

    try:
        result = push_db(_db_path, _api_url, _api_key, force=True, retries=1)
        logging.info("auto-push ok: %s", result)
    except Exception as e:
        logging.error("auto-push failed: %s", e)
        sys.exit(1)
