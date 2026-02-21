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
