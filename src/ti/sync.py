"""Import Twitter JSON into SQLite with UPSERT deduplication."""

import sqlite3
import time
from pathlib import Path

from ti.parser import parse_file
from ti.db import rebuild_fts


def sync_file(conn: sqlite3.Connection, path: Path) -> dict:
    start = time.monotonic()
    users, tweets = parse_file(path)

    if not tweets:
        return {"inserted": 0, "updated": 0, "source_file": path.name}

    inserted = 0
    updated = 0

    for user in users:
        conn.execute(
            """INSERT INTO users (user_id, screen_name, name, profile_image_url)
               VALUES (:user_id, :screen_name, :name, :profile_image_url)
               ON CONFLICT(user_id) DO UPDATE SET
                 screen_name = excluded.screen_name,
                 name = excluded.name,
                 profile_image_url = excluded.profile_image_url,
                 updated_at = datetime('now')""",
            user,
        )

    for tweet in tweets:
        tweet["source_file"] = path.name
        # Pre-check existence for accurate insert/update counting
        exists = conn.execute(
            "SELECT 1 FROM tweets WHERE id = ?", (tweet["id"],)
        ).fetchone()

        conn.execute(
            """INSERT INTO tweets
               (id, created_at, full_text, user_id, url, lang, conversation_id,
                quoted_tweet_id, favorite_count, retweet_count, bookmark_count,
                quote_count, reply_count, views_count, media_json, module, source_file)
               VALUES
               (:id, :created_at, :full_text, :user_id, :url, :lang, :conversation_id,
                :quoted_tweet_id, :favorite_count, :retweet_count, :bookmark_count,
                :quote_count, :reply_count, :views_count, :media_json, :module, :source_file)
               ON CONFLICT(id) DO UPDATE SET
                 favorite_count = excluded.favorite_count,
                 retweet_count = excluded.retweet_count,
                 bookmark_count = excluded.bookmark_count,
                 quote_count = excluded.quote_count,
                 reply_count = excluded.reply_count,
                 views_count = excluded.views_count,
                 updated_at = datetime('now')""",
            tweet,
        )
        if exists:
            updated += 1
        else:
            inserted += 1

    # Update metadata watermark
    latest = max(tweets, key=lambda t: t["id"])
    conn.execute(
        "INSERT INTO metadata (key, value) VALUES ('latest_tweet_id', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = "
        "CASE WHEN CAST(excluded.value AS INTEGER) > CAST(value AS INTEGER) "
        "THEN excluded.value ELSE value END",
        (latest["id"],),
    )
    conn.execute(
        "INSERT INTO metadata (key, value) VALUES ('latest_tweet_date', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = "
        "CASE WHEN excluded.value > value THEN excluded.value ELSE value END",
        (latest["created_at"],),
    )

    duration_ms = int((time.monotonic() - start) * 1000)

    conn.execute(
        """INSERT INTO import_log
           (source_file, file_size_bytes, tweets_inserted, tweets_updated, duration_ms)
           VALUES (?, ?, ?, ?, ?)""",
        (path.name, path.stat().st_size, inserted, updated, duration_ms),
    )

    conn.commit()
    rebuild_fts(conn)

    return {
        "inserted": inserted,
        "updated": updated,
        "source_file": path.name,
        "duration_ms": duration_ms,
    }
