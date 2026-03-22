"""Full schema validation for pushed databases."""

import sqlite3
from pathlib import Path

REQUIRED_TABLES = {"users", "tweets", "tags", "tweet_tags", "metadata", "import_log"}

REQUIRED_TWEET_COLUMNS = {
    "id",
    "created_at",
    "full_text",
    "user_id",
    "primary_tag",
    "favorite_count",
    "bookmark_count",
    "views_count",
}


def validate_pushed_db(db_path: Path) -> list[str]:
    """Validate a pushed database. Returns list of error strings (empty = valid)."""
    errors = []
    try:
        conn = sqlite3.connect(str(db_path))
    except Exception as e:
        return [f"Cannot open database: {e}"]

    try:
        result = conn.execute("PRAGMA integrity_check").fetchone()
        if result[0] != "ok":
            errors.append(f"Integrity check failed: {result[0]}")
            return errors

        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        missing_tables = REQUIRED_TABLES - tables
        if missing_tables:
            errors.append(f"Missing tables: {', '.join(sorted(missing_tables))}")
            return errors

        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(tweets)").fetchall()
        }
        missing_cols = REQUIRED_TWEET_COLUMNS - columns
        if missing_cols:
            errors.append(
                f"Missing columns on tweets: {', '.join(sorted(missing_cols))}"
            )

        try:
            conn.execute("SELECT * FROM tweets_fts LIMIT 1")
        except Exception as e:
            errors.append(f"FTS5 check failed: {e}")

        try:
            row = conn.execute(
                "SELECT value FROM metadata WHERE key='schema_version'"
            ).fetchone()
            if row:
                version = int(row[0])
                expected = 1
                if version > expected:
                    errors.append(
                        f"Schema version {version} > expected {expected}. Upgrade server first."
                    )
        except Exception:
            pass
    except Exception as e:
        errors.append(f"Validation error: {e}")
    finally:
        conn.close()

    return errors
