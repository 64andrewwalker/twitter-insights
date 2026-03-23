import json
from ti.output import format_stats, format_tags, format_remote_results, OutputFormat

SAMPLE_STATS = {
    "total_tweets": 408,
    "classified": 340,
    "unclassified": 68,
    "authors": 231,
    "date_range_from": "2024-11-20",
    "date_range_to": "2026-02-25",
    "latest_tweet_id": "2026564921429839991",
}

SAMPLE_TAGS = [
    {"name": "claude-code-workflow", "category": "claude-code", "count": 45},
    {"name": "mcp", "category": "tools-and-ecosystem", "count": 20},
    {"name": "offbeat", "category": "meta-and-noise", "count": 0},
]


def test_format_stats_json():
    output = format_stats(SAMPLE_STATS, fmt=OutputFormat.JSON)
    data = json.loads(output)
    assert data["command"] == "stats"
    assert data["total_tweets"] == 408
    assert data["classified"] == 340
    assert data["date_range"]["from"] == "2024-11-20"


def test_format_stats_brief():
    output = format_stats(SAMPLE_STATS, fmt=OutputFormat.BRIEF)
    assert "408" in output
    assert "340" in output


def test_format_stats_human():
    output = format_stats(SAMPLE_STATS, fmt=OutputFormat.HUMAN)
    assert "408" in output


def test_format_tags_json():
    output = format_tags(SAMPLE_TAGS, fmt=OutputFormat.JSON)
    data = json.loads(output)
    assert data["command"] == "tags"
    assert data["total"] == 3
    assert data["results"][0]["name"] == "claude-code-workflow"


def test_format_tags_brief():
    output = format_tags(SAMPLE_TAGS, fmt=OutputFormat.BRIEF)
    assert "claude-code-workflow: 45" in output
    assert "offbeat" not in output


def test_format_tags_human():
    output = format_tags(SAMPLE_TAGS, fmt=OutputFormat.HUMAN)
    assert "claude-code-workflow" in output


def test_format_remote_results_brief():
    data = {
        "command": "search",
        "total": 1,
        "returned": 1,
        "offset": 0,
        "results": [
            {
                "id": "t1",
                "author": "@alice",
                "text": "hello world",
                "primary_tag": "mcp",
                "created_at": "2026-01-01T12:00:00Z",
                "url": "",
                "engagement": {"likes": 10, "bookmarks": 5, "views": 100},
            }
        ],
    }
    output = format_remote_results(command="search", data=data, fmt=OutputFormat.BRIEF)
    assert "t1" in output
    assert "@alice" in output


def test_format_remote_results_human():
    data = {
        "command": "search",
        "total": 1,
        "returned": 1,
        "offset": 0,
        "results": [
            {
                "id": "t1",
                "author": "@alice",
                "text": "hello world",
                "primary_tag": "mcp",
                "created_at": "2026-01-01T12:00:00Z",
                "url": "",
                "engagement": {"likes": 10, "bookmarks": 5, "views": 100},
            }
        ],
    }
    output = format_remote_results(command="search", data=data, fmt=OutputFormat.HUMAN)
    assert "alice" in output
