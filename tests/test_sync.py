import json
import pytest
from ti.sync import sync_file

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
