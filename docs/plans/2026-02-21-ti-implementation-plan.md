# Twitter Insights CLI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a CLI tool (`ti`) that imports Twitter likes JSON, classifies tweets with AI, and provides searchable access for humans and agents.

**Architecture:** Python CLI (Typer) backed by SQLite + FTS5 trigram. Classification dispatched via `codebridge submit --model haiku`. All output supports `--format human|json|brief` for agent consumption.

**Tech Stack:** Python 3.12, Typer 0.21, Rich, SQLite 3.51 (FTS5 trigram), codebridge CLI

**Design Doc:** `docs/plans/2026-02-21-twitter-insights-design.md`

---

## Project Layout

```
twitter-insights/
├── pyproject.toml
├── src/ti/
│   ├── __init__.py
│   ├── cli.py           # Typer app entry, all commands
│   ├── db.py            # Schema, connection, migrations
│   ├── parser.py        # Twitter JSON → clean dicts
│   ├── sync.py          # Import + UPSERT dedup
│   ├── search.py        # FTS5 search + tag/author queries
│   ├── classify.py      # codebridge dispatch for Haiku classification
│   ├── output.py        # Formatting: human (Rich), JSON, brief
│   └── taxonomy.py      # Tag definitions (32 tags, 7 categories)
├── tests/
│   ├── conftest.py      # Fixtures: temp DB, sample tweets
│   ├── test_db.py
│   ├── test_parser.py
│   ├── test_sync.py
│   ├── test_search.py
│   └── test_output.py
└── docs/plans/
```

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/ti/__init__.py`
- Create: `src/ti/cli.py`

**Step 1: Create pyproject.toml**

```toml
[project]
name = "twitter-insights"
version = "0.1.0"
description = "CLI tool for searching curated Twitter insights"
requires-python = ">=3.12"
dependencies = [
    "typer>=0.21",
    "rich>=13.0",
]

[project.scripts]
ti = "ti.cli:app"

[build-system]
requires = ["setuptools>=75"]
build-backend = "setuptools.backends._legacy:_Backend"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

**Step 2: Create minimal CLI entry point**

`src/ti/__init__.py`: empty file

`src/ti/cli.py`:
```python
import typer

app = typer.Typer(
    name="ti",
    help="Twitter Insights - search and browse curated tweet knowledge base",
    no_args_is_help=True,
)


@app.command()
def stats():
    """Show database statistics."""
    typer.echo("ti is working")


if __name__ == "__main__":
    app()
```

**Step 3: Install in dev mode and verify**

Run: `pip install -e .`
Run: `ti --help`
Expected: Shows help with `stats` command listed

Run: `ti stats`
Expected: Prints "ti is working"

**Step 4: Commit**

```bash
git add pyproject.toml src/
git commit -m "feat: project scaffolding with Typer CLI entry point"
```

---

### Task 2: Database Schema

**Files:**
- Create: `src/ti/db.py`
- Create: `src/ti/taxonomy.py`
- Create: `tests/conftest.py`
- Create: `tests/test_db.py`

**Step 1: Write the taxonomy module**

`src/ti/taxonomy.py` — the tag definitions as plain data:
```python
"""Tag taxonomy: 7 categories, 32 tags."""

TAXONOMY: dict[str, dict[str, str]] = {
    "claude-code": {
        "claude-code-workflow": "Usage patterns, session management, context strategies, CLAUDE.md",
        "claude-code-skills": "Skills/SKILL.md, skill repos, Context7, Vercel skills",
        "claude-code-hooks": "Hooks, plugins, pre/post hooks",
        "claude-code-memory": "Memory persistence, context carryover",
        "claude-code-tools": "Third-party tools, wrappers, IDEs integrating CC",
    },
    "agent-engineering": {
        "multi-agent-orchestration": "Multi-agent setups, sub-agents, orchestrator patterns",
        "agent-memory": "Agent memory architecture, persistent memory systems",
        "agent-autonomy": "Autonomous agents, always-on assistants",
        "agent-browser": "Browser automation for agents",
        "agent-sdk": "Agent SDKs, programmatic agent construction",
    },
    "llm-models": {
        "model-comparison": "Side-by-side rankings, benchmarks",
        "model-release": "New model announcements",
        "api-access": "API pricing, proxies, subscription strategies",
        "local-models": "Local inference, GPU selection, VRAM",
    },
    "vibe-coding": {
        "vibe-coding-workflow": "AI-assisted dev process",
        "vibe-coding-ui": "AI-generated frontend, design tools",
        "vibe-coding-philosophy": "Opinions on AI coding quality, future of SE",
    },
    "tools-and-ecosystem": {
        "mcp": "Model Context Protocol servers, setup",
        "prompt-engineering": "System prompt design, CLAUDE.md optimization",
        "open-source": "Open-source project highlights",
        "devtools": "Non-AI dev tooling (tmux, monorepo, GitHub Actions)",
        "ai-product-design": "AI-native product design philosophy",
    },
    "specific-products": {
        "cursor": "Cursor IDE",
        "openclaw": "OpenClaw/Clawdbot/MoltBot/NanoClaw",
        "opencode": "Opencode, Oh My OpenCode",
        "gemini-ecosystem": "Gemini CLI, Google AI, Chrome integration",
        "codex": "OpenAI Codex CLI, AGENTS.md",
        "kimi": "Kimi/Moonshot AI models",
    },
    "meta-and-noise": {
        "ai-industry": "Industry news, layoffs, enterprise AI",
        "learning-resources": "Reading lists, paper summaries, podcast recs",
        "offbeat": "Personal life, health tips, off-topic",
    },
}

ALL_TAGS: dict[str, str] = {}
for category, tags in TAXONOMY.items():
    for tag_name, description in tags.items():
        ALL_TAGS[tag_name] = category


def get_category(tag_name: str) -> str | None:
    return ALL_TAGS.get(tag_name)
```

**Step 2: Write the database module**

`src/ti/db.py`:
```python
"""SQLite database: schema creation, connection, seed tags."""

import sqlite3
from pathlib import Path

from ti.taxonomy import TAXONOMY

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "ti.db"

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


def get_connection(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
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
```

**Step 3: Write tests**

`tests/conftest.py`:
```python
import sqlite3
import pytest
from ti.db import init_db


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    init_db(conn)
    yield conn
    conn.close()
```

`tests/test_db.py`:
```python
from ti.db import init_db, rebuild_fts
from ti.taxonomy import TAXONOMY, ALL_TAGS


def test_schema_creates_all_tables(db):
    tables = {
        row[0]
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert {"users", "tweets", "tags", "tweet_tags", "import_log", "metadata"} <= tables


def test_fts_table_exists(db):
    tables = {
        row[0]
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "tweets_fts" in tables


def test_tags_seeded(db):
    count = db.execute("SELECT COUNT(*) FROM tags").fetchone()[0]
    assert count == len(ALL_TAGS)
    assert count == 32


def test_tags_have_correct_categories(db):
    rows = db.execute("SELECT name, category FROM tags").fetchall()
    for row in rows:
        assert row["category"] in TAXONOMY
        assert row["name"] in TAXONOMY[row["category"]]


def test_idempotent_init(db):
    init_db(db)
    init_db(db)
    count = db.execute("SELECT COUNT(*) FROM tags").fetchone()[0]
    assert count == 32


def test_rebuild_fts_empty(db):
    rebuild_fts(db)
```

**Step 4: Run tests**

Run: `python3 -m pytest tests/test_db.py -v`
Expected: All 6 tests PASS

**Step 5: Commit**

```bash
git add src/ti/db.py src/ti/taxonomy.py tests/
git commit -m "feat: database schema with FTS5 trigram and 32-tag taxonomy"
```

---

### Task 3: Twitter JSON Parser

**Files:**
- Create: `src/ti/parser.py`
- Create: `tests/test_parser.py`

**Step 1: Write tests**

`tests/test_parser.py`:
```python
import json
import pytest
from ti.parser import parse_tweet, parse_file, validate_json


SAMPLE_TWEET = {
    "id": "2025033171864354981",
    "module": "likes",
    "created_at": "2026-02-21 10:21:46",
    "full_text": "Cloudflare Code Mode 测试",
    "media": [],
    "screen_name": "shao__meng",
    "name": "meng shao",
    "profile_image_url": "https://example.com/avatar.jpg",
    "user_id": "123456",
    "in_reply_to": "",
    "retweeted_status": "",
    "quoted_status": "12345",
    "media_tags": [],
    "tags": [],
    "module_sort_indices": {"likes": "123"},
    "favorite_count": 27,
    "retweet_count": 9,
    "bookmark_count": 30,
    "quote_count": 1,
    "reply_count": 3,
    "views_count": 3644,
    "favorited": True,
    "retweeted": False,
    "bookmarked": False,
    "url": "https://twitter.com/shao__meng/status/2025033171864354981",
    "raw": {
        "legacy": {
            "conversation_id_str": "2025033171864354981",
            "lang": "zh",
        }
    },
}


def test_parse_tweet_extracts_fields():
    user, tweet = parse_tweet(SAMPLE_TWEET)
    assert tweet["id"] == "2025033171864354981"
    assert tweet["full_text"] == "Cloudflare Code Mode 测试"
    assert tweet["user_id"] == "123456"
    assert tweet["favorite_count"] == 27
    assert tweet["views_count"] == 3644
    assert tweet["url"] == "https://twitter.com/shao__meng/status/2025033171864354981"
    assert tweet["lang"] == "zh"
    assert tweet["conversation_id"] == "2025033171864354981"
    assert tweet["quoted_tweet_id"] == "12345"


def test_parse_tweet_extracts_user():
    user, tweet = parse_tweet(SAMPLE_TWEET)
    assert user["user_id"] == "123456"
    assert user["screen_name"] == "shao__meng"
    assert user["name"] == "meng shao"


def test_parse_tweet_normalizes_date():
    user, tweet = parse_tweet(SAMPLE_TWEET)
    assert tweet["created_at"] == "2026-02-21T10:21:46Z"


def test_parse_tweet_empty_quoted_status():
    t = {**SAMPLE_TWEET, "quoted_status": ""}
    _, tweet = parse_tweet(t)
    assert tweet["quoted_tweet_id"] is None


def test_parse_tweet_serializes_media():
    t = {**SAMPLE_TWEET, "media": [{"type": "photo", "url": "https://x.com/img.jpg"}]}
    _, tweet = parse_tweet(t)
    assert json.loads(tweet["media_json"]) == [{"type": "photo", "url": "https://x.com/img.jpg"}]


def test_validate_json_rejects_non_array(tmp_path):
    f = tmp_path / "bad.json"
    f.write_text('{"not": "array"}')
    with pytest.raises(ValueError, match="array"):
        validate_json(f)


def test_validate_json_rejects_missing_fields(tmp_path):
    f = tmp_path / "bad.json"
    f.write_text('[{"foo": "bar"}]')
    with pytest.raises(ValueError, match="required field"):
        validate_json(f)


def test_parse_file(tmp_path):
    f = tmp_path / "tweets.json"
    f.write_text(json.dumps([SAMPLE_TWEET]))
    users, tweets = parse_file(f)
    assert len(users) == 1
    assert len(tweets) == 1
```

**Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_parser.py -v`
Expected: FAIL (ImportError — parser module doesn't exist)

**Step 3: Implement parser**

`src/ti/parser.py`:
```python
"""Parse Twitter JSON export files into clean dicts for DB insertion."""

import json
from pathlib import Path

REQUIRED_FIELDS = {"id", "module", "created_at", "full_text", "screen_name"}


def validate_json(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Expected JSON array, got {type(data).__name__}")
    if len(data) == 0:
        return data
    first = data[0]
    for field in REQUIRED_FIELDS:
        if field not in first:
            raise ValueError(f"Missing required field: {field}")
    return data


def parse_tweet(raw_tweet: dict) -> tuple[dict, dict]:
    user = {
        "user_id": raw_tweet["user_id"],
        "screen_name": raw_tweet["screen_name"],
        "name": raw_tweet.get("name", ""),
        "profile_image_url": raw_tweet.get("profile_image_url", ""),
    }

    # Normalize date: "2026-02-21 10:21:46" → "2026-02-21T10:21:46Z"
    created_at = raw_tweet["created_at"].replace(" ", "T") + "Z"

    # Extract lang and conversation_id from raw.legacy if available
    legacy = raw_tweet.get("raw", {}).get("legacy", {})
    lang = legacy.get("lang")
    conversation_id = legacy.get("conversation_id_str")

    # quoted_status: "" → None
    quoted = raw_tweet.get("quoted_status", "")
    quoted_tweet_id = quoted if quoted else None

    # Serialize media
    media = raw_tweet.get("media", [])
    media_json = json.dumps(media, ensure_ascii=False) if media else "[]"

    tweet = {
        "id": raw_tweet["id"],
        "created_at": created_at,
        "full_text": raw_tweet["full_text"],
        "user_id": raw_tweet["user_id"],
        "url": raw_tweet.get("url", ""),
        "lang": lang,
        "conversation_id": conversation_id,
        "quoted_tweet_id": quoted_tweet_id,
        "favorite_count": raw_tweet.get("favorite_count", 0),
        "retweet_count": raw_tweet.get("retweet_count", 0),
        "bookmark_count": raw_tweet.get("bookmark_count", 0),
        "quote_count": raw_tweet.get("quote_count", 0),
        "reply_count": raw_tweet.get("reply_count", 0),
        "views_count": raw_tweet.get("views_count", 0),
        "media_json": media_json,
        "module": raw_tweet.get("module", "likes"),
    }

    return user, tweet


def parse_file(path: Path) -> tuple[list[dict], list[dict]]:
    data = validate_json(path)
    users = []
    tweets = []
    seen_users = set()
    for raw_tweet in data:
        user, tweet = parse_tweet(raw_tweet)
        if user["user_id"] not in seen_users:
            users.append(user)
            seen_users.add(user["user_id"])
        tweets.append(tweet)
    return users, tweets
```

**Step 4: Run tests**

Run: `python3 -m pytest tests/test_parser.py -v`
Expected: All 9 tests PASS

**Step 5: Commit**

```bash
git add src/ti/parser.py tests/test_parser.py
git commit -m "feat: Twitter JSON parser with validation and date normalization"
```

---

### Task 4: Sync Command (Import + UPSERT Dedup)

**Files:**
- Create: `src/ti/sync.py`
- Create: `tests/test_sync.py`
- Modify: `src/ti/cli.py`

**Step 1: Write tests**

`tests/test_sync.py`:
```python
import json
import pytest
from ti.sync import sync_file
from ti.db import init_db

TWEET_A = {
    "id": "100", "module": "likes", "created_at": "2026-01-01 12:00:00",
    "full_text": "Tweet A about Claude Code", "media": [], "screen_name": "alice",
    "name": "Alice", "profile_image_url": "", "user_id": "u1",
    "in_reply_to": "", "retweeted_status": "", "quoted_status": "",
    "media_tags": [], "tags": [], "module_sort_indices": {},
    "favorite_count": 10, "retweet_count": 2, "bookmark_count": 5,
    "quote_count": 0, "reply_count": 1, "views_count": 1000,
    "favorited": True, "retweeted": False, "bookmarked": False,
    "url": "https://twitter.com/alice/status/100",
    "raw": {"legacy": {"lang": "en", "conversation_id_str": "100"}},
}

TWEET_B = {
    **TWEET_A, "id": "200", "full_text": "Tweet B about MCP",
    "favorite_count": 20, "views_count": 5000,
    "url": "https://twitter.com/alice/status/200",
    "raw": {"legacy": {"lang": "zh", "conversation_id_str": "200"}},
}


def test_sync_inserts_new_tweets(db, tmp_path):
    f = tmp_path / "tweets.json"
    f.write_text(json.dumps([TWEET_A, TWEET_B]))
    result = sync_file(db, f)
    assert result["inserted"] == 2
    assert result["updated"] == 0
    count = db.execute("SELECT COUNT(*) FROM tweets").fetchone()[0]
    assert count == 2


def test_sync_upserts_engagement(db, tmp_path):
    f = tmp_path / "tweets.json"
    f.write_text(json.dumps([TWEET_A]))
    sync_file(db, f)

    updated = {**TWEET_A, "favorite_count": 99, "views_count": 9999}
    f.write_text(json.dumps([updated]))
    result = sync_file(db, f)
    assert result["inserted"] == 0
    assert result["updated"] == 1

    row = db.execute("SELECT favorite_count, views_count FROM tweets WHERE id='100'").fetchone()
    assert row["favorite_count"] == 99
    assert row["views_count"] == 9999


def test_sync_preserves_classification(db, tmp_path):
    f = tmp_path / "tweets.json"
    f.write_text(json.dumps([TWEET_A]))
    sync_file(db, f)

    db.execute("UPDATE tweets SET primary_tag='mcp', confidence=0.9 WHERE id='100'")
    db.commit()

    updated = {**TWEET_A, "favorite_count": 50}
    f.write_text(json.dumps([updated]))
    sync_file(db, f)

    row = db.execute("SELECT primary_tag, confidence FROM tweets WHERE id='100'").fetchone()
    assert row["primary_tag"] == "mcp"
    assert row["confidence"] == 0.9


def test_sync_creates_users(db, tmp_path):
    f = tmp_path / "tweets.json"
    f.write_text(json.dumps([TWEET_A]))
    sync_file(db, f)
    user = db.execute("SELECT * FROM users WHERE user_id='u1'").fetchone()
    assert user["screen_name"] == "alice"


def test_sync_logs_import(db, tmp_path):
    f = tmp_path / "tweets.json"
    f.write_text(json.dumps([TWEET_A, TWEET_B]))
    sync_file(db, f)
    log = db.execute("SELECT * FROM import_log ORDER BY id DESC LIMIT 1").fetchone()
    assert log["tweets_inserted"] == 2
    assert log["source_file"] == "tweets.json"


def test_sync_updates_metadata(db, tmp_path):
    f = tmp_path / "tweets.json"
    f.write_text(json.dumps([TWEET_A, TWEET_B]))
    sync_file(db, f)
    latest = db.execute("SELECT value FROM metadata WHERE key='latest_tweet_id'").fetchone()
    assert latest["value"] == "200"


def test_sync_validates_bad_json(db, tmp_path):
    f = tmp_path / "bad.json"
    f.write_text('{"not": "array"}')
    with pytest.raises(ValueError):
        sync_file(db, f)


def test_sync_empty_file(db, tmp_path):
    f = tmp_path / "empty.json"
    f.write_text("[]")
    result = sync_file(db, f)
    assert result["inserted"] == 0
```

**Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_sync.py -v`
Expected: FAIL (ImportError)

**Step 3: Implement sync**

`src/ti/sync.py`:
```python
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
        cur = conn.execute(
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
        if cur.rowcount == 1:
            # Check if it was an insert or update by seeing if changes is 1
            # For INSERT, rowid is new; for UPDATE, it updates existing
            existing = conn.execute(
                "SELECT imported_at, updated_at FROM tweets WHERE id = ?",
                (tweet["id"],),
            ).fetchone()
            if existing["imported_at"] == existing["updated_at"]:
                inserted += 1
            else:
                updated += 1

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
```

> **Note:** The insert/update detection via comparing `imported_at == updated_at` is a heuristic. For `ON CONFLICT DO UPDATE`, SQLite always sets `rowcount=1` whether it inserts or updates. The `updated_at` defaults to `datetime('now')` on insert, and is explicitly set to `datetime('now')` on update — but within the same transaction second they can be equal. A more robust approach: query existence first with `SELECT 1 FROM tweets WHERE id = ?` before the UPSERT. The implementing engineer should choose the cleaner approach — pre-check vs. post-check. Pre-check is simpler:

```python
exists = conn.execute("SELECT 1 FROM tweets WHERE id = ?", (tweet["id"],)).fetchone()
conn.execute("INSERT ... ON CONFLICT ...", tweet)
if exists:
    updated += 1
else:
    inserted += 1
```

**Step 4: Run tests**

Run: `python3 -m pytest tests/test_sync.py -v`
Expected: All 8 tests PASS

**Step 5: Wire sync command into CLI**

Update `src/ti/cli.py` to add the `sync` command:
```python
import typer
from pathlib import Path
from rich.console import Console
from ti.db import get_connection, init_db

app = typer.Typer(
    name="ti",
    help="Twitter Insights - search and browse curated tweet knowledge base",
    no_args_is_help=True,
)
console = Console()


def _get_db():
    conn = get_connection()
    init_db(conn)
    return conn


@app.command()
def sync(
    file: Path = typer.Argument(..., help="Path to Twitter JSON export file"),
):
    """Import tweets from a JSON export file."""
    if not file.exists():
        console.print(f"[red]File not found: {file}[/red]")
        raise typer.Exit(1)

    from ti.sync import sync_file

    conn = _get_db()
    result = sync_file(conn, file)
    conn.close()

    console.print(
        f"[green]Synced {file.name}:[/green] "
        f"{result['inserted']} new, {result['updated']} updated "
        f"({result['duration_ms']}ms)"
    )


@app.command()
def stats():
    """Show database statistics."""
    conn = _get_db()
    total = conn.execute("SELECT COUNT(*) FROM tweets").fetchone()[0]
    users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    classified = conn.execute(
        "SELECT COUNT(*) FROM tweets WHERE primary_tag IS NOT NULL"
    ).fetchone()[0]
    unclassified = total - classified

    dates = conn.execute(
        "SELECT MIN(created_at), MAX(created_at) FROM tweets"
    ).fetchone()

    latest = conn.execute(
        "SELECT value FROM metadata WHERE key='latest_tweet_id'"
    ).fetchone()

    console.print(f"[bold]Twitter Insights Database[/bold]")
    console.print(f"  Tweets: {total} ({classified} classified, {unclassified} pending)")
    console.print(f"  Authors: {users}")
    if dates[0]:
        console.print(f"  Date range: {dates[0]} → {dates[1]}")
    if latest:
        console.print(f"  Latest tweet ID: {latest[0]}")
    conn.close()


if __name__ == "__main__":
    app()
```

**Step 6: Test CLI end-to-end**

Run: `ti sync /Volumes/DevWork/homebrew/twitter-insights/twitter-tweets-1771658347735.json`
Expected: "Synced twitter-tweets-1771658347735.json: 340 new, 0 updated (Xms)"

Run: `ti stats`
Expected: Shows 340 tweets, 202 authors, date range, latest tweet ID

Run: `ti sync /Volumes/DevWork/homebrew/twitter-insights/twitter-tweets-1771658347735.json`
Expected: "Synced ...: 0 new, 340 updated (Xms)" (dedup working)

**Step 7: Commit**

```bash
git add src/ti/sync.py src/ti/cli.py tests/test_sync.py
git commit -m "feat: sync command with UPSERT dedup and import logging"
```

---

### Task 5: Output Formatting Module

**Files:**
- Create: `src/ti/output.py`
- Create: `tests/test_output.py`

**Step 1: Write tests**

`tests/test_output.py`:
```python
import json
import pytest
from ti.output import format_results, OutputFormat

SAMPLE_ROW = {
    "id": "100",
    "created_at": "2026-01-01T12:00:00Z",
    "full_text": "A tweet about Claude Code workflows",
    "summary": "Claude Code workflow tips",
    "screen_name": "alice",
    "name": "Alice",
    "url": "https://twitter.com/alice/status/100",
    "primary_tag": "claude-code-workflow",
    "confidence": 0.92,
    "favorite_count": 10,
    "bookmark_count": 5,
    "views_count": 1000,
    "tags": "claude-code-workflow,claude-code-tools",
}


def test_json_format():
    output = format_results(
        command="search",
        results=[SAMPLE_ROW],
        total=1,
        fmt=OutputFormat.JSON,
        query="Claude",
    )
    data = json.loads(output)
    assert data["command"] == "search"
    assert data["total"] == 1
    assert data["returned"] == 1
    assert data["results"][0]["id"] == "100"
    assert data["results"][0]["author"] == "@alice"
    assert data["results"][0]["engagement"]["likes"] == 10


def test_brief_format():
    output = format_results(
        command="search",
        results=[SAMPLE_ROW],
        total=1,
        fmt=OutputFormat.BRIEF,
    )
    assert "100" in output
    assert "@alice" in output


def test_human_format():
    output = format_results(
        command="search",
        results=[SAMPLE_ROW],
        total=1,
        fmt=OutputFormat.HUMAN,
    )
    assert "alice" in output
    assert "Claude Code" in output or "Claude" in output
```

**Step 2: Implement output module**

`src/ti/output.py`:
```python
"""Output formatting: human (Rich), JSON envelope, brief."""

import json
from enum import Enum

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


class OutputFormat(str, Enum):
    HUMAN = "human"
    JSON = "json"
    BRIEF = "brief"


def _row_to_result(row: dict) -> dict:
    tags_str = row.get("tags", "")
    tags = [t for t in tags_str.split(",") if t] if isinstance(tags_str, str) else []
    return {
        "id": row["id"],
        "author": f"@{row['screen_name']}",
        "author_name": row.get("name", ""),
        "created_at": row["created_at"],
        "text": row["full_text"],
        "summary": row.get("summary"),
        "url": row.get("url", ""),
        "tags": tags,
        "primary_tag": row.get("primary_tag"),
        "confidence": row.get("confidence"),
        "engagement": {
            "likes": row.get("favorite_count", 0),
            "bookmarks": row.get("bookmark_count", 0),
            "views": row.get("views_count", 0),
        },
    }


def format_results(
    command: str,
    results: list[dict],
    total: int,
    fmt: OutputFormat = OutputFormat.HUMAN,
    query: str | None = None,
    offset: int = 0,
) -> str:
    if fmt == OutputFormat.JSON:
        envelope = {
            "command": command,
            "total": total,
            "returned": len(results),
            "offset": offset,
            "results": [_row_to_result(r) for r in results],
        }
        if query is not None:
            envelope["query"] = query
        return json.dumps(envelope, ensure_ascii=False, indent=2)

    if fmt == OutputFormat.BRIEF:
        lines = []
        for r in results:
            tag = r.get("primary_tag", "?")
            lines.append(
                f"[{tag}] {r['id']} @{r['screen_name']} "
                f"{r['full_text'][:80]}..."
            )
        if total > len(results) + offset:
            lines.append(f"\n({total} total, showing {offset+1}-{offset+len(results)})")
        return "\n".join(lines)

    # Human format with Rich
    console = Console(width=100, force_terminal=False)
    with console.capture() as capture:
        for r in results:
            tag = r.get("primary_tag", "unclassified")
            conf = r.get("confidence")
            conf_str = f" ({conf:.0%})" if conf else ""
            header = f"@{r['screen_name']} · {r['created_at'][:10]} · [{tag}{conf_str}]"

            text = r["full_text"]
            if len(text) > 300:
                text = text[:300] + "..."

            summary = r.get("summary")
            body = f"{text}\n"
            if summary:
                body += f"\n📌 {summary}\n"
            body += (
                f"\n❤️ {r.get('favorite_count',0):,}  "
                f"🔖 {r.get('bookmark_count',0):,}  "
                f"👁 {r.get('views_count',0):,}  "
                f"🔗 {r.get('url','')}"
            )

            console.print(Panel(body, title=header, border_style="dim"))

        if total > len(results) + offset:
            console.print(
                f"\nShowing {offset+1}-{offset+len(results)} of {total}. "
                f"Use --offset {offset+len(results)} to see more.",
                style="dim",
            )

    return capture.get()


def print_output(output: str, fmt: OutputFormat) -> None:
    if fmt == OutputFormat.HUMAN:
        console = Console()
        console.print(output, highlight=False)
    else:
        print(output)
```

**Step 3: Run tests**

Run: `python3 -m pytest tests/test_output.py -v`
Expected: All 3 tests PASS

**Step 4: Commit**

```bash
git add src/ti/output.py tests/test_output.py
git commit -m "feat: output formatting with JSON envelope, brief, and Rich human mode"
```

---

### Task 6: Search, Tag, Author, Show, Latest Commands

**Files:**
- Create: `src/ti/search.py`
- Create: `tests/test_search.py`
- Modify: `src/ti/cli.py`

**Step 1: Write tests**

`tests/test_search.py`:
```python
import json
import pytest
from ti.db import init_db, rebuild_fts
from ti.sync import sync_file

TWEETS = [
    {
        "id": "100", "module": "likes", "created_at": "2026-01-01 10:00:00",
        "full_text": "Claude Code is amazing for agent development",
        "media": [], "screen_name": "alice", "name": "Alice",
        "profile_image_url": "", "user_id": "u1",
        "in_reply_to": "", "retweeted_status": "", "quoted_status": "",
        "media_tags": [], "tags": [], "module_sort_indices": {},
        "favorite_count": 100, "retweet_count": 10, "bookmark_count": 50,
        "quote_count": 5, "reply_count": 3, "views_count": 10000,
        "favorited": True, "retweeted": False, "bookmarked": False,
        "url": "https://twitter.com/alice/status/100",
        "raw": {"legacy": {"lang": "en", "conversation_id_str": "100"}},
    },
    {
        "id": "200", "module": "likes", "created_at": "2026-01-15 10:00:00",
        "full_text": "MCP server 最佳实践分享",
        "media": [], "screen_name": "bob", "name": "Bob",
        "profile_image_url": "", "user_id": "u2",
        "in_reply_to": "", "retweeted_status": "", "quoted_status": "",
        "media_tags": [], "tags": [], "module_sort_indices": {},
        "favorite_count": 200, "retweet_count": 20, "bookmark_count": 80,
        "quote_count": 2, "reply_count": 5, "views_count": 20000,
        "favorited": True, "retweeted": False, "bookmarked": False,
        "url": "https://twitter.com/bob/status/200",
        "raw": {"legacy": {"lang": "zh", "conversation_id_str": "200"}},
    },
    {
        "id": "300", "module": "likes", "created_at": "2026-02-01 10:00:00",
        "full_text": "Building agents with Claude Code skills and hooks",
        "media": [], "screen_name": "alice", "name": "Alice",
        "profile_image_url": "", "user_id": "u1",
        "in_reply_to": "", "retweeted_status": "", "quoted_status": "",
        "media_tags": [], "tags": [], "module_sort_indices": {},
        "favorite_count": 50, "retweet_count": 5, "bookmark_count": 30,
        "quote_count": 1, "reply_count": 2, "views_count": 5000,
        "favorited": True, "retweeted": False, "bookmarked": False,
        "url": "https://twitter.com/alice/status/300",
        "raw": {"legacy": {"lang": "en", "conversation_id_str": "300"}},
    },
]


@pytest.fixture
def populated_db(db, tmp_path):
    f = tmp_path / "tweets.json"
    f.write_text(json.dumps(TWEETS))
    sync_file(db, f)
    # Add tags to tweet 100
    db.execute("UPDATE tweets SET primary_tag='claude-code-workflow', confidence=0.9 WHERE id='100'")
    tag_id = db.execute("SELECT id FROM tags WHERE name='claude-code-workflow'").fetchone()[0]
    db.execute("INSERT INTO tweet_tags (tweet_id, tag_id) VALUES ('100', ?)", (tag_id,))
    # Add tags to tweet 200
    db.execute("UPDATE tweets SET primary_tag='mcp', confidence=0.85 WHERE id='200'")
    tag_id2 = db.execute("SELECT id FROM tags WHERE name='mcp'").fetchone()[0]
    db.execute("INSERT INTO tweet_tags (tweet_id, tag_id) VALUES ('200', ?)", (tag_id2,))
    db.commit()
    rebuild_fts(db)
    return db


def test_fts_search(populated_db):
    from ti.search import fts_search
    results, total = fts_search(populated_db, "Claude Code")
    assert total >= 1
    assert any(r["id"] == "100" for r in results)


def test_fts_search_chinese(populated_db):
    from ti.search import fts_search
    results, total = fts_search(populated_db, "MCP")
    assert total >= 1
    assert any(r["id"] == "200" for r in results)


def test_tag_filter(populated_db):
    from ti.search import by_tag
    results, total = by_tag(populated_db, "claude-code-workflow")
    assert total == 1
    assert results[0]["id"] == "100"


def test_author_filter(populated_db):
    from ti.search import by_author
    results, total = by_author(populated_db, "alice")
    assert total == 2


def test_show_tweet(populated_db):
    from ti.search import show_tweet
    result = show_tweet(populated_db, "100")
    assert result is not None
    assert result["id"] == "100"


def test_latest(populated_db):
    from ti.search import latest_tweets
    results, total = latest_tweets(populated_db, limit=2)
    assert len(results) == 2
    assert results[0]["id"] == "300"  # Most recent first
```

**Step 2: Implement search module**

`src/ti/search.py`:
```python
"""Query functions: FTS search, tag filter, author filter, etc."""

import sqlite3

_BASE_SELECT = """
    SELECT t.*, u.screen_name, u.name,
           GROUP_CONCAT(tg.name) as tags
    FROM tweets t
    JOIN users u ON t.user_id = u.user_id
    LEFT JOIN tweet_tags tt ON t.id = tt.tweet_id
    LEFT JOIN tags tg ON tt.tag_id = tg.id
"""

_GROUP_BY = "GROUP BY t.id"


def fts_search(
    conn: sqlite3.Connection,
    query: str,
    limit: int = 20,
    offset: int = 0,
    sort: str = "relevant",
) -> tuple[list[dict], int]:
    # Count total matches
    count_row = conn.execute(
        "SELECT COUNT(*) FROM tweets_fts WHERE tweets_fts MATCH ?",
        (query,),
    ).fetchone()
    total = count_row[0]

    if sort == "recent":
        order = "t.created_at DESC"
    elif sort == "popular":
        order = "(t.bookmark_count + t.favorite_count) DESC"
    else:
        order = "rank"

    rows = conn.execute(
        f"""SELECT t.*, u.screen_name, u.name,
                   GROUP_CONCAT(tg.name) as tags,
                   tweets_fts.rank as rank
            FROM tweets_fts
            JOIN tweets t ON tweets_fts.rowid = t.rowid
            JOIN users u ON t.user_id = u.user_id
            LEFT JOIN tweet_tags tt ON t.id = tt.tweet_id
            LEFT JOIN tags tg ON tt.tag_id = tg.id
            WHERE tweets_fts MATCH ?
            {_GROUP_BY}
            ORDER BY {order}
            LIMIT ? OFFSET ?""",
        (query, limit, offset),
    ).fetchall()

    return [dict(r) for r in rows], total


def by_tag(
    conn: sqlite3.Connection,
    tag_name: str,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict], int]:
    count_row = conn.execute(
        """SELECT COUNT(DISTINCT t.id)
           FROM tweets t
           JOIN tweet_tags tt ON t.id = tt.tweet_id
           JOIN tags tg ON tt.tag_id = tg.id
           WHERE tg.name = ? OR t.primary_tag = ?""",
        (tag_name, tag_name),
    ).fetchone()
    total = count_row[0]

    rows = conn.execute(
        f"""{_BASE_SELECT}
            WHERE tg.name = ? OR t.primary_tag = ?
            {_GROUP_BY}
            ORDER BY t.created_at DESC
            LIMIT ? OFFSET ?""",
        (tag_name, tag_name, limit, offset),
    ).fetchall()

    return [dict(r) for r in rows], total


def by_author(
    conn: sqlite3.Connection,
    screen_name: str,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict], int]:
    # Strip @ if present
    screen_name = screen_name.lstrip("@")
    count_row = conn.execute(
        """SELECT COUNT(*) FROM tweets t
           JOIN users u ON t.user_id = u.user_id
           WHERE u.screen_name = ?""",
        (screen_name,),
    ).fetchone()
    total = count_row[0]

    rows = conn.execute(
        f"""{_BASE_SELECT}
            WHERE u.screen_name = ?
            {_GROUP_BY}
            ORDER BY t.created_at DESC
            LIMIT ? OFFSET ?""",
        (screen_name, limit, offset),
    ).fetchall()

    return [dict(r) for r in rows], total


def show_tweet(conn: sqlite3.Connection, tweet_id: str) -> dict | None:
    row = conn.execute(
        f"""{_BASE_SELECT}
            WHERE t.id = ?
            {_GROUP_BY}""",
        (tweet_id,),
    ).fetchone()
    return dict(row) if row else None


def latest_tweets(
    conn: sqlite3.Connection,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict], int]:
    total = conn.execute("SELECT COUNT(*) FROM tweets").fetchone()[0]
    rows = conn.execute(
        f"""{_BASE_SELECT}
            {_GROUP_BY}
            ORDER BY t.created_at DESC
            LIMIT ? OFFSET ?""",
        (limit, offset),
    ).fetchall()
    return [dict(r) for r in rows], total


def list_tags(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """SELECT tg.name, tg.category, COUNT(tt.tweet_id) as count
           FROM tags tg
           LEFT JOIN tweet_tags tt ON tg.id = tt.tag_id
           GROUP BY tg.id
           ORDER BY count DESC, tg.category, tg.name"""
    ).fetchall()
    return [dict(r) for r in rows]
```

**Step 3: Run tests**

Run: `python3 -m pytest tests/test_search.py -v`
Expected: All 6 tests PASS

**Step 4: Wire all commands into CLI**

Update `src/ti/cli.py` — add all query commands with `--format`, `--limit`, `--offset` support. The full CLI should have: `sync`, `search`, `tag`, `tags`, `author`, `show`, `latest`, `stats`.

Each command follows the pattern:
1. Parse args
2. Call search function
3. Format with `format_results()`
4. Print output

Use a shared callback for the global `--format`, `--limit`, `--offset` options via Typer's `@app.callback()`.

**Step 5: Test CLI end-to-end**

Run: `ti search "Claude Code" --format json | python3 -m json.tool`
Run: `ti latest 5`
Run: `ti author dotey`
Run: `ti show 2025033171864354981`
Run: `ti tags`

**Step 6: Commit**

```bash
git add src/ti/search.py src/ti/cli.py tests/test_search.py
git commit -m "feat: search, tag, author, show, latest, tags commands"
```

---

### Task 7: Classify Command (codebridge + Haiku)

**Files:**
- Create: `src/ti/classify.py`
- Modify: `src/ti/cli.py`

**Step 1: Write classify module**

`src/ti/classify.py` orchestrates classification:

1. Query unclassified tweets from DB
2. Batch them (10-20 per batch)
3. Build the classification prompt (taxonomy + glossary + tweet batch)
4. Submit each batch via `codebridge submit --engine claude-code --model haiku --wait`
5. Parse `result.json` summary → extract JSON classifications
6. Write results back to DB (primary_tag, confidence, summary, lang, tweet_tags)

The classification prompt template should include:
- Full tag taxonomy with descriptions
- Chinese tech glossary: `cc=Claude Code, 龙虾=OpenClaw, 反代=reverse proxy, 内卷=competitive pressure, 赛博=cyber, 技能栈=skills stack`
- The batch of tweets as a JSON array
- Expected output format: `[{"id": "...", "primary_tag": "...", "tags": [...], "confidence": 0.0-1.0, "summary": "one line", "lang": "zh|en|mixed|ja"}]`

**Step 2: Implement classify command in CLI**

```
ti classify              # Classify all unclassified tweets
ti classify --retry      # Retry failed classifications
ti classify --batch-size 15  # Customize batch size
ti classify --dry-run    # Show what would be classified without doing it
```

**Step 3: Test with real data**

Run: `ti classify --dry-run`
Expected: Shows count of tweets to classify

Run: `ti classify --batch-size 10`
Expected: Submits batches via codebridge, prints progress, updates DB

Run: `ti stats`
Expected: Shows classified count increased

Run: `ti tags`
Expected: Shows tags with non-zero counts

**Step 4: Commit**

```bash
git add src/ti/classify.py src/ti/cli.py
git commit -m "feat: classify command with codebridge + Haiku batch dispatch"
```

---

### Task 8: Final Polish

**Files:**
- Modify: `src/ti/cli.py`
- Create: `CLAUDE.md`

**Step 1: Add `ti sync --dir` support**

Add `--dir` flag to `sync` that globs `*.json` in a directory and processes each file.

**Step 2: Add `ti ask` command**

`ti ask "how to optimize MCP server"`:
1. Call codebridge/haiku to expand the question into FTS search terms + relevant tags
2. Run FTS search with expanded terms
3. Return matching tweets (no generated answer — just retrieval)

**Step 3: Create CLAUDE.md**

Project-level CLAUDE.md with:
- What this project is
- How to run (`ti --help`)
- How to sync new data
- How to classify
- DB location
- How agents should query (`ti search --format json`)

**Step 4: Commit**

```bash
git add -A
git commit -m "feat: sync --dir, ask command, and CLAUDE.md"
```

---

## Execution Notes

- **DB location:** `ti.db` in project root (gitignored)
- **JSON data files:** gitignored (`twitter-tweets-*.json`)
- **codebridge daemon:** Not needed if using `--wait` (synchronous). For parallel: `codebridge start --max-concurrent 4`
- **FTS rebuild:** Happens automatically after each `sync`. For manual: `python3 -c "from ti.db import *; rebuild_fts(get_connection())"`
- **Re-classification:** Delete tag data with `UPDATE tweets SET primary_tag=NULL, confidence=NULL WHERE ...` then run `ti classify`
