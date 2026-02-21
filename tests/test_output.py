import json
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
