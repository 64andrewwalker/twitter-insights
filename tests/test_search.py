import json
import pytest
from ti.db import rebuild_fts
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
        "full_text": "MCP server best practices sharing",
        "media": [], "screen_name": "bob", "name": "Bob",
        "profile_image_url": "", "user_id": "u2",
        "in_reply_to": "", "retweeted_status": "", "quoted_status": "",
        "media_tags": [], "tags": [], "module_sort_indices": {},
        "favorite_count": 200, "retweet_count": 20, "bookmark_count": 80,
        "quote_count": 2, "reply_count": 5, "views_count": 20000,
        "favorited": True, "retweeted": False, "bookmarked": False,
        "url": "https://twitter.com/bob/status/200",
        "raw": {"legacy": {"lang": "en", "conversation_id_str": "200"}},
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
    # Add classification to tweet 100
    db.execute("UPDATE tweets SET primary_tag='claude-code-workflow', confidence=0.9 WHERE id='100'")
    tag_id = db.execute("SELECT id FROM tags WHERE name='claude-code-workflow'").fetchone()[0]
    db.execute("INSERT INTO tweet_tags (tweet_id, tag_id) VALUES ('100', ?)", (tag_id,))
    # Add classification to tweet 200
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


def test_fts_search_mcp(populated_db):
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
    assert results[0]["id"] == "300"
