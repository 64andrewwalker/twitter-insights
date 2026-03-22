"""SQLite database: schema creation, connection, seed tags."""

import sqlite3
from pathlib import Path

from ti.config import resolve_db_path
from ti.taxonomy import TAXONOMY

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    screen_name TEXT NOT NULL,
    name TEXT,
    profile_image_url TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tweets (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    full_text TEXT NOT NULL,
    summary TEXT,
    lang TEXT,
    user_id TEXT NOT NULL REFERENCES users(user_id),
    url TEXT,
    favorite_count INTEGER DEFAULT 0,
    retweet_count INTEGER DEFAULT 0,
    bookmark_count INTEGER DEFAULT 0,
    quote_count INTEGER DEFAULT 0,
    reply_count INTEGER DEFAULT 0,
    views_count INTEGER DEFAULT 0,
    quoted_tweet_id TEXT,
    conversation_id TEXT,
    media_json TEXT,
    module TEXT DEFAULT 'likes',
    primary_tag TEXT,
    confidence REAL,
    classification_error TEXT,
    source_file TEXT,
    imported_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    category TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tweet_tags (
    tweet_id TEXT NOT NULL REFERENCES tweets(id),
    tag_id INTEGER NOT NULL REFERENCES tags(id),
    PRIMARY KEY (tweet_id, tag_id)
);

CREATE TABLE IF NOT EXISTS import_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    imported_at TEXT NOT NULL DEFAULT (datetime('now')),
    source_file TEXT,
    file_size_bytes INTEGER,
    tweets_inserted INTEGER DEFAULT 0,
    tweets_updated INTEGER DEFAULT 0,
    tweets_classified INTEGER DEFAULT 0,
    classification_errors INTEGER DEFAULT 0,
    duration_ms INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE INDEX IF NOT EXISTS idx_tweets_user_id ON tweets(user_id);
CREATE INDEX IF NOT EXISTS idx_tweets_created_at ON tweets(created_at);
CREATE INDEX IF NOT EXISTS idx_tweets_module ON tweets(module);
CREATE INDEX IF NOT EXISTS idx_tweets_primary_tag ON tweets(primary_tag);
CREATE INDEX IF NOT EXISTS idx_tweets_unclassified ON tweets(id) WHERE primary_tag IS NULL;
CREATE INDEX IF NOT EXISTS idx_tweet_tags_tag_id ON tweet_tags(tag_id);
CREATE INDEX IF NOT EXISTS idx_tweet_tags_reverse ON tweet_tags(tag_id, tweet_id);
"""

FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS tweets_fts USING fts5(
    full_text,
    summary,
    content='tweets',
    content_rowid='rowid',
    tokenize='trigram'
);
"""


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    if db_path is None:
        db_path = resolve_db_path()
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.executescript(FTS_SQL)
    _seed_tags(conn)
    conn.commit()


def _seed_tags(conn: sqlite3.Connection) -> None:
    for category, tags in TAXONOMY.items():
        for tag_name in tags:
            conn.execute(
                "INSERT OR IGNORE INTO tags (name, category) VALUES (?, ?)",
                (tag_name, category),
            )


def rebuild_fts(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO tweets_fts(tweets_fts) VALUES('rebuild')")
    conn.commit()
