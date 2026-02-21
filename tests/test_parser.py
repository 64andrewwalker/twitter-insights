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
