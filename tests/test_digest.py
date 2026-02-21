# tests/test_digest.py
import json
import sqlite3
from datetime import date

import pytest
from ti.db import init_db, rebuild_fts
from ti.sync import sync_file
from ti.digest import get_period_range, get_period_label

# --- Task 1: Date range tests ---


def test_weekly_range_mid_week():
    start, end = get_period_range("weekly", ref_date=date(2026, 2, 18))
    assert start == date(2026, 2, 16)
    assert end == date(2026, 2, 22)


def test_weekly_range_monday():
    start, end = get_period_range("weekly", ref_date=date(2026, 2, 16))
    assert start == date(2026, 2, 16)
    assert end == date(2026, 2, 22)


def test_weekly_range_sunday():
    start, end = get_period_range("weekly", ref_date=date(2026, 2, 22))
    assert start == date(2026, 2, 16)
    assert end == date(2026, 2, 22)


def test_monthly_range():
    start, end = get_period_range("monthly", ref_date=date(2026, 2, 15))
    assert start == date(2026, 2, 1)
    assert end == date(2026, 2, 28)


def test_period_label_weekly():
    label = get_period_label("weekly", date(2026, 2, 16), date(2026, 2, 22))
    assert "2026" in label
    assert "W08" in label


def test_period_label_monthly():
    label = get_period_label("monthly", date(2026, 2, 1), date(2026, 2, 28))
    assert "2026-02" in label


# --- Task 2: Query and grouping fixtures/tests ---

DIGEST_TWEETS = [
    {
        "id": "100",
        "module": "likes",
        "created_at": "2026-02-18 10:00:00",
        "full_text": "Claude Code is amazing for agent development",
        "media": [],
        "screen_name": "alice",
        "name": "Alice",
        "profile_image_url": "",
        "user_id": "u1",
        "in_reply_to": "",
        "retweeted_status": "",
        "quoted_status": "",
        "media_tags": [],
        "tags": [],
        "module_sort_indices": {},
        "favorite_count": 100,
        "retweet_count": 10,
        "bookmark_count": 50,
        "quote_count": 5,
        "reply_count": 3,
        "views_count": 10000,
        "favorited": True,
        "retweeted": False,
        "bookmarked": False,
        "url": "https://twitter.com/alice/status/100",
        "raw": {"legacy": {"lang": "en", "conversation_id_str": "100"}},
    },
    {
        "id": "200",
        "module": "likes",
        "created_at": "2026-02-19 10:00:00",
        "full_text": "MCP server best practices sharing",
        "media": [],
        "screen_name": "bob",
        "name": "Bob",
        "profile_image_url": "",
        "user_id": "u2",
        "in_reply_to": "",
        "retweeted_status": "",
        "quoted_status": "",
        "media_tags": [],
        "tags": [],
        "module_sort_indices": {},
        "favorite_count": 200,
        "retweet_count": 20,
        "bookmark_count": 80,
        "quote_count": 2,
        "reply_count": 5,
        "views_count": 20000,
        "favorited": True,
        "retweeted": False,
        "bookmarked": False,
        "url": "https://twitter.com/bob/status/200",
        "raw": {"legacy": {"lang": "en", "conversation_id_str": "200"}},
    },
    {
        "id": "300",
        "module": "likes",
        "created_at": "2026-02-20 10:00:00",
        "full_text": "Another Claude Code workflow tip",
        "media": [],
        "screen_name": "charlie",
        "name": "Charlie",
        "profile_image_url": "",
        "user_id": "u3",
        "in_reply_to": "",
        "retweeted_status": "",
        "quoted_status": "",
        "media_tags": [],
        "tags": [],
        "module_sort_indices": {},
        "favorite_count": 50,
        "retweet_count": 5,
        "bookmark_count": 30,
        "quote_count": 1,
        "reply_count": 2,
        "views_count": 5000,
        "favorited": True,
        "retweeted": False,
        "bookmarked": False,
        "url": "https://twitter.com/charlie/status/300",
        "raw": {"legacy": {"lang": "en", "conversation_id_str": "300"}},
    },
]


@pytest.fixture
def digest_db(tmp_path):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    init_db(conn)
    f = tmp_path / "tweets.json"
    f.write_text(json.dumps(DIGEST_TWEETS))
    sync_file(conn, f)
    for tid in ("100", "300"):
        conn.execute(
            "UPDATE tweets SET primary_tag='claude-code-workflow', "
            "confidence=0.9, summary='CC workflow insight', lang='en' WHERE id=?",
            (tid,),
        )
        tag_id = conn.execute(
            "SELECT id FROM tags WHERE name='claude-code-workflow'"
        ).fetchone()[0]
        conn.execute(
            "INSERT OR IGNORE INTO tweet_tags (tweet_id, tag_id) VALUES (?, ?)",
            (tid, tag_id),
        )
    conn.execute(
        "UPDATE tweets SET primary_tag='mcp', confidence=0.85, "
        "summary='MCP best practices', lang='en' WHERE id='200'"
    )
    tag_id = conn.execute("SELECT id FROM tags WHERE name='mcp'").fetchone()[0]
    conn.execute(
        "INSERT OR IGNORE INTO tweet_tags (tweet_id, tag_id) VALUES ('200', ?)",
        (tag_id,),
    )
    conn.commit()
    rebuild_fts(conn)
    yield conn
    conn.close()


def test_query_tweets_in_range(digest_db):
    from ti.digest import query_tweets_in_range

    tweets = query_tweets_in_range(digest_db, "2026-02-16", "2026-02-22")
    assert len(tweets) == 3
    assert all(t["screen_name"] for t in tweets)


def test_query_tweets_excludes_out_of_range(digest_db):
    from ti.digest import query_tweets_in_range

    tweets = query_tweets_in_range(digest_db, "2026-03-01", "2026-03-07")
    assert len(tweets) == 0


def test_group_by_category(digest_db):
    from ti.digest import query_tweets_in_range, group_by_category

    tweets = query_tweets_in_range(digest_db, "2026-02-16", "2026-02-22")
    groups = group_by_category(tweets)
    assert "claude-code" in groups
    assert "tools-and-ecosystem" in groups
    assert len(groups["claude-code"]) == 2
    assert len(groups["tools-and-ecosystem"]) == 1


def test_group_sorted_by_engagement(digest_db):
    from ti.digest import query_tweets_in_range, group_by_category

    tweets = query_tweets_in_range(digest_db, "2026-02-16", "2026-02-22")
    groups = group_by_category(tweets)
    cc_tweets = groups["claude-code"]
    assert cc_tweets[0]["id"] == "100"


def test_unclassified_detection(digest_db):
    from ti.digest import query_tweets_in_range

    digest_db.execute("UPDATE tweets SET primary_tag=NULL, summary=NULL WHERE id='300'")
    digest_db.commit()
    tweets = query_tweets_in_range(digest_db, "2026-02-16", "2026-02-22")
    unclassified = [t for t in tweets if t["primary_tag"] is None]
    assert len(unclassified) == 1
    assert unclassified[0]["id"] == "300"


# --- Task 3: Prompt builder and response parser ---


def test_build_digest_prompt():
    from ti.digest import build_digest_prompt

    groups = {
        "claude-code": [
            {
                "id": "100",
                "screen_name": "alice",
                "summary": "CC workflow tip",
                "primary_tag": "claude-code-workflow",
            },
            {
                "id": "300",
                "screen_name": "charlie",
                "summary": "Another CC tip",
                "primary_tag": "claude-code-workflow",
            },
        ],
        "tools-and-ecosystem": [
            {
                "id": "200",
                "screen_name": "bob",
                "summary": "MCP best practices",
                "primary_tag": "mcp",
            },
        ],
    }
    prompt = build_digest_prompt(groups, "2026-W08")
    assert "ADHD" in prompt
    assert "claude-code" in prompt
    assert "CC workflow tip" in prompt
    assert "JSON" in prompt


def test_parse_digest_response_valid():
    from ti.digest import parse_digest_response

    raw = '{"tldr": "Big week for CC", "topics": [{"category": "claude-code", "headline": "CC is hot", "commentary": "Everyone is talking about it", "must_read": ["100"], "vibe": "hot"}], "hot_take": "AI is eating the world"}'
    result = parse_digest_response(raw)
    assert result["tldr"] == "Big week for CC"
    assert len(result["topics"]) == 1
    assert result["topics"][0]["vibe"] == "hot"
    assert result["hot_take"] == "AI is eating the world"


def test_parse_digest_response_from_markdown():
    from ti.digest import parse_digest_response

    raw = 'Here is the digest:\n```json\n{"tldr": "Test", "topics": [], "hot_take": null}\n```\n'
    result = parse_digest_response(raw)
    assert result["tldr"] == "Test"


def test_parse_digest_response_invalid():
    from ti.digest import parse_digest_response

    with pytest.raises(ValueError):
        parse_digest_response("not json at all")


# --- Task 4: Data assembly ---


def test_assemble_digest_data(digest_db):
    from ti.digest import assemble_digest_data

    ai_response = {
        "tldr": "Big week",
        "topics": [
            {
                "category": "claude-code",
                "headline": "CC is hot",
                "commentary": "Great stuff",
                "must_read": ["100"],
                "vibe": "hot",
            },
            {
                "category": "tools-and-ecosystem",
                "headline": "MCP grows",
                "commentary": "Steady progress",
                "must_read": [],
                "vibe": "steady",
            },
        ],
        "hot_take": "AI wins",
    }
    data = assemble_digest_data(
        digest_db,
        period="weekly",
        start_date="2026-02-16",
        end_date="2026-02-22",
        ai_response=ai_response,
    )
    assert data["period"] == "2026-W08"
    assert data["tldr"] == "Big week"
    assert data["hot_take"] == "AI wins"
    assert data["stats"]["total_tweets"] == 3
    assert len(data["topics"]) == 2
    cc_topic = next(t for t in data["topics"] if t["category"] == "claude-code")
    assert len(cc_topic["tweets"]) == 2
    assert cc_topic["tweets"][0]["must_read"] is True
    assert cc_topic["tweets"][1]["must_read"] is False


# --- Task 5-6: HTML template and renderer ---


def test_render_html(tmp_path):
    from ti.digest import render_digest_html

    data = {
        "period": "2026-W08",
        "period_label": "2026-W08 (2月16日 - 2月22日)",
        "generated_at": "2026-02-21T21:00:00",
        "stats": {
            "total_tweets": 3,
            "total_authors": 2,
            "date_range": ["2026-02-16", "2026-02-22"],
        },
        "tldr": "Test digest",
        "hot_take": None,
        "topics": [],
    }
    out_path = tmp_path / "digest.html"
    render_digest_html(data, out_path)
    content = out_path.read_text()
    assert "Test digest" in content
    assert "ReactDOM" in content
    assert "{{DATA}}" not in content
