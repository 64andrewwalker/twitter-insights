"""FastAPI application for ti-server."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from server.auth import verify_api_key
from server.db import DBManager


def _rate_limit_key(request: Request) -> str:
    return request.headers.get("X-API-Key", get_remote_address(request))


def create_app(db_path: Path | None = None) -> FastAPI:
    app = FastAPI(title="ti-server", docs_url=None, redoc_url=None)
    pool = DBManager(db_path)

    # Validate API key length at startup (spec: minimum 32 chars)
    from server.auth import get_api_keys

    startup_keys = get_api_keys()
    if startup_keys:
        for k in startup_keys:
            if len(k) < 32:
                raise RuntimeError(
                    f"API key must be at least 32 characters (got {len(k)})"
                )

    limiter = Limiter(key_func=_rate_limit_key)
    app.state.limiter = limiter

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content={"error": "rate_limited", "message": "Too many requests"},
        )

    @app.middleware("http")
    async def add_cache_control(request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    def require_auth(x_api_key: str | None):
        if not x_api_key or not verify_api_key(x_api_key):
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "unauthorized",
                    "message": "Invalid API key",
                },
            )

    def get_conn() -> sqlite3.Connection:
        try:
            return pool.get_connection()
        except FileNotFoundError:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "service_unavailable",
                    "message": "Database not initialized. Run: ti db push",
                },
            )

    # Reuse query functions from ti package
    from ti.search import (
        by_author,
        by_tag,
        fts_search,
        latest_tweets,
        list_tags,
        show_tweet,
    )
    from ti.output import _row_to_result

    def _envelope(command, results, total, offset=0, query=None):
        env = {
            "command": command,
            "total": total,
            "returned": len(results),
            "offset": offset,
            "results": [_row_to_result(r) for r in results],
        }
        if query is not None:
            env["query"] = query
        return env

    # ── Health (unauthenticated) ──────────────────────────────────

    @app.get("/health")
    def health():
        return {"status": "ok", "db_ready": pool.db_ready}

    # ── Authenticated read endpoints ──────────────────────────────

    @app.get("/v1/search")
    @limiter.limit("60/minute")
    def search(
        request: Request,
        q: str,
        sort: str = "relevant",
        limit: int = 20,
        offset: int = 0,
        x_api_key: str | None = Header(None),
    ):
        require_auth(x_api_key)
        if sort not in ("relevant", "recent", "popular"):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "bad_request",
                    "message": "sort must be one of: relevant, recent, popular",
                },
            )
        limit = max(1, min(100, limit))
        offset = max(0, offset)
        conn = get_conn()
        results, total = fts_search(conn, q, limit=limit, offset=offset, sort=sort)
        return _envelope("search", results, total, offset, query=q)

    @app.get("/v1/tag/{name}")
    @limiter.limit("60/minute")
    def tag(
        request: Request,
        name: str,
        limit: int = 20,
        offset: int = 0,
        x_api_key: str | None = Header(None),
    ):
        require_auth(x_api_key)
        limit = max(1, min(100, limit))
        offset = max(0, offset)
        conn = get_conn()
        results, total = by_tag(conn, name, limit=limit, offset=offset)
        return _envelope("tag", results, total, offset, query=name)

    @app.get("/v1/tags")
    @limiter.limit("60/minute")
    def tags(request: Request, x_api_key: str | None = Header(None)):
        require_auth(x_api_key)
        conn = get_conn()
        tag_list = list_tags(conn)
        return {"command": "tags", "total": len(tag_list), "results": tag_list}

    @app.get("/v1/author/{handle}")
    @limiter.limit("60/minute")
    def author(
        request: Request,
        handle: str,
        limit: int = 20,
        offset: int = 0,
        x_api_key: str | None = Header(None),
    ):
        require_auth(x_api_key)
        limit = max(1, min(100, limit))
        offset = max(0, offset)
        conn = get_conn()
        results, total = by_author(conn, handle, limit=limit, offset=offset)
        return _envelope("author", results, total, offset, query=handle)

    @app.get("/v1/show/{tweet_id}")
    @limiter.limit("60/minute")
    def show(
        request: Request,
        tweet_id: str,
        x_api_key: str | None = Header(None),
    ):
        require_auth(x_api_key)
        conn = get_conn()
        result = show_tweet(conn, tweet_id)
        if not result:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "not_found",
                    "message": f"Tweet {tweet_id} not found",
                },
            )
        return _envelope("show", [result], 1)

    @app.get("/v1/latest")
    @limiter.limit("60/minute")
    def latest(
        request: Request,
        n: int = 20,
        offset: int = 0,
        x_api_key: str | None = Header(None),
    ):
        require_auth(x_api_key)
        n = max(1, min(100, n))
        offset = max(0, offset)
        conn = get_conn()
        results, total = latest_tweets(conn, limit=n, offset=offset)
        return _envelope("latest", results, total, offset)

    @app.get("/v1/stats")
    @limiter.limit("60/minute")
    def stats(request: Request, x_api_key: str | None = Header(None)):
        require_auth(x_api_key)
        conn = get_conn()
        total = conn.execute("SELECT COUNT(*) FROM tweets").fetchone()[0]
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        classified = conn.execute(
            "SELECT COUNT(*) FROM tweets WHERE primary_tag IS NOT NULL"
        ).fetchone()[0]
        dates = conn.execute(
            "SELECT MIN(created_at), MAX(created_at) FROM tweets"
        ).fetchone()
        latest_row = conn.execute(
            "SELECT value FROM metadata WHERE key='latest_tweet_id'"
        ).fetchone()
        return {
            "command": "stats",
            "total_tweets": total,
            "classified": classified,
            "unclassified": total - classified,
            "authors": users,
            "date_range": {"from": dates[0] or "", "to": dates[1] or ""},
            "latest_tweet_id": latest_row[0] if latest_row else "",
            "last_push_at": pool.last_push_at or "",
            "db_version": pool.last_push_at or "",
        }

    # ── DB management endpoints ───────────────────────────────────

    @app.post("/v1/db/push")
    async def db_push(
        file: UploadFile,
        x_api_key: str | None = Header(None),
        x_ti_force_push: str | None = Header(None),
        x_ti_db_version: str | None = Header(None),
    ):
        require_auth(x_api_key)
        from uuid import uuid4

        from server.r2 import archive_db
        from server.validate import validate_pushed_db

        force = x_ti_force_push and x_ti_force_push.lower() == "true"
        if not force and x_ti_db_version and pool.last_push_at:
            if x_ti_db_version != pool.last_push_at:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "conflict",
                        "message": "Remote DB was updated since your last sync",
                        "remote_version": pool.last_push_at,
                        "your_version": x_ti_db_version,
                    },
                )

        max_size = 50 * 1024 * 1024
        temp_path = Path(pool.db_path.parent) / f"ti-{uuid4().hex[:8]}.db"

        try:
            total_bytes = 0
            with open(temp_path, "wb") as f:
                while chunk := await file.read(64 * 1024):
                    total_bytes += len(chunk)
                    if total_bytes > max_size:
                        temp_path.unlink(missing_ok=True)
                        raise HTTPException(
                            status_code=413,
                            detail="Payload too large (max 50MB)",
                        )
                    f.write(chunk)

            errors = validate_pushed_db(temp_path)
            if errors:
                temp_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=422,
                    detail={"error": "validation_failed", "errors": errors},
                )

            r2_version = archive_db(temp_path)

            tmp_conn = sqlite3.connect(str(temp_path))
            tweet_count = tmp_conn.execute("SELECT COUNT(*) FROM tweets").fetchone()[0]
            tmp_conn.close()

            version_ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
            with pool.write_lock:
                temp_path.rename(pool.db_path)
                pool.swap_db()
                pool.last_push_at = version_ts

            return {
                "version": r2_version or version_ts,
                "size_bytes": total_bytes,
                "tweet_count": tweet_count,
                "r2_archived": r2_version is not None,
            }
        except HTTPException:
            raise
        except OSError as e:
            temp_path.unlink(missing_ok=True)
            if "No space" in str(e) or "Disk quota" in str(e):
                raise HTTPException(status_code=507, detail="Storage full")
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            temp_path.unlink(missing_ok=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/v1/db/versions")
    @limiter.limit("60/minute")
    def db_versions(
        request: Request,
        limit: int = 10,
        x_api_key: str | None = Header(None),
    ):
        require_auth(x_api_key)
        from server.r2 import list_versions

        return {"versions": list_versions(limit)}

    @app.post("/v1/db/restore")
    def db_restore(
        version: str | None = None,
        x_api_key: str | None = Header(None),
    ):
        require_auth(x_api_key)
        from uuid import uuid4

        from server.r2 import download_version, list_versions
        from server.validate import validate_pushed_db

        if not version:
            versions = list_versions(1)
            if not versions:
                raise HTTPException(status_code=404, detail="No backups available")
            version = versions[0]["version"]

        temp_path = Path(pool.db_path.parent) / f"ti-restore-{uuid4().hex[:8]}.db"
        if not download_version(version, temp_path):
            raise HTTPException(
                status_code=404,
                detail=f"Version {version} not found in R2",
            )

        errors = validate_pushed_db(temp_path)
        if errors:
            temp_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=422,
                detail={"error": "validation_failed", "errors": errors},
            )

        restore_ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with pool.write_lock:
            temp_path.rename(pool.db_path)
            pool.swap_db()
            pool.last_push_at = restore_ts

        return {"restored_version": version}

    return app
