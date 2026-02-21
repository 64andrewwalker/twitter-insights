# `ti digest` Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `ti digest` command that generates a visually appealing HTML digest of recent tweets, grouped by topic with AI commentary.

**Architecture:** Python queries DB by date range, groups tweets by tag category, sends summaries to AI via codebridge for commentary, then injects structured JSON into a self-contained React+Tailwind HTML template and opens it in the browser.

**Tech Stack:** Python (typer, sqlite3), codebridge CLI (AI), React 18 + Tailwind CSS via CDN (HTML template)

**Design doc:** `docs/plans/2026-02-21-digest-command-design.md`

---

## BDD Scenarios (Acceptance Criteria)

All implementation tasks are driven by these behavior scenarios. Each task references which scenario(s) it satisfies.

```gherkin
Feature: Twitter Insights Digest

  Scenario: Generate weekly digest with AI commentary
    Given tweets collected during the current week
    And all tweets are classified with tags and summaries
    When the user runs "ti digest"
    Then they see a digest page in the browser
    And the page shows a TL;DR that hooks their attention
    And tweets are grouped by topic with AI-written headlines
    And each topic has opinionated commentary
    And must-read tweets are highlighted

  Scenario: Auto-classify before digest generation
    Given tweets collected during the current week
    And some tweets have not been classified yet
    When the user runs "ti digest"
    Then unclassified tweets are classified automatically first
    And then the digest is generated with all tweets included

  Scenario: No tweets in period
    Given no tweets were collected this week
    When the user runs "ti digest"
    Then they see a message saying no tweets found

  Scenario: Dry run shows what would be digested
    Given tweets collected during the current week
    When the user runs "ti digest --dry-run"
    Then they see the tweet count and category breakdown
    And no AI call is made
    And no HTML file is generated

  Scenario: JSON output for agent consumption
    Given tweets collected during the current week
    When the user runs "ti digest --format json"
    Then they receive a JSON object with tldr, topics, and tweets
    And no browser is opened

  Scenario: Save digest to permanent file
    Given a generated digest
    When the user runs "ti digest --save"
    Then the HTML is also saved to digests/ directory
    And the filename matches the period

  Scenario: Monthly digest
    Given tweets collected during the current month
    When the user runs "ti digest --period monthly"
    Then the digest covers the entire month

  Scenario: Visual appearance of the digest page
    Given a generated digest HTML page open in the browser
    Then the page has a dark theme background
    And the TL;DR appears in a prominent card at the top
    And each topic section shows a headline, vibe badge, and commentary
    And tweet cards display author, summary, engagement stats, and link
    And must-read tweets have a golden highlight border and "必看" badge
    And the hot take section has an orange accent border
    And the layout is responsive with a card grid
```

### Scenario → Task Mapping

| Scenario               | Tasks                  |
| ---------------------- | ---------------------- |
| Generate weekly digest | 1, 2, 3, 4, 5, 6, 7, 8 |
| Auto-classify          | 8                      |
| No tweets in period    | 8                      |
| Dry run                | 8                      |
| JSON output            | 4, 8                   |
| Save to file           | 8                      |
| Monthly digest         | 1                      |
| Visual appearance      | 5, 10                  |

### Visual Verification Strategy

Task 10 uses AI vision to verify the "Visual appearance" scenario:

1. Generate HTML with realistic mock data (3 topics, 8+ tweets, must-reads, hot take)
2. Use Playwright to screenshot the page (headless Chrome)
3. Send screenshot to AI (Claude via Read tool, or Gemini via codebridge/opencode) for verification against the visual scenario checklist
4. AI confirms or flags issues

This replaces pixel-perfect snapshot tests with semantic visual understanding.

---

### Task 1: Date Range Utilities

**Files:**

- Create: `src/ti/digest.py`
- Create: `tests/test_digest.py`

**Step 1: Write the failing tests for date range calculation**

```python
# tests/test_digest.py
from datetime import date
from ti.digest import get_period_range


def test_weekly_range_mid_week():
    """Wednesday 2026-02-18 should give Mon 2026-02-16 to Sun 2026-02-22."""
    start, end = get_period_range("weekly", ref_date=date(2026, 2, 18))
    assert start == date(2026, 2, 16)
    assert end == date(2026, 2, 22)


def test_weekly_range_monday():
    """Monday should be start of its own week."""
    start, end = get_period_range("weekly", ref_date=date(2026, 2, 16))
    assert start == date(2026, 2, 16)
    assert end == date(2026, 2, 22)


def test_weekly_range_sunday():
    """Sunday should be end of its week."""
    start, end = get_period_range("weekly", ref_date=date(2026, 2, 22))
    assert start == date(2026, 2, 16)
    assert end == date(2026, 2, 22)


def test_monthly_range():
    """February 2026 has 28 days."""
    start, end = get_period_range("monthly", ref_date=date(2026, 2, 15))
    assert start == date(2026, 2, 1)
    assert end == date(2026, 2, 28)


def test_period_label_weekly():
    from ti.digest import get_period_label
    label = get_period_label("weekly", date(2026, 2, 16), date(2026, 2, 22))
    assert "2026" in label
    assert "W08" in label


def test_period_label_monthly():
    from ti.digest import get_period_label
    label = get_period_label("monthly", date(2026, 2, 1), date(2026, 2, 28))
    assert "2026-02" in label
```

**Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_digest.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ti.digest'`

**Step 3: Implement date range utilities**

```python
# src/ti/digest.py
"""Digest generation: query, group, AI commentary, HTML rendering."""

import calendar
from datetime import date, timedelta


def get_period_range(
    period: str, ref_date: date | None = None
) -> tuple[date, date]:
    """Return (start, end) dates for the given period containing ref_date."""
    if ref_date is None:
        ref_date = date.today()

    if period == "monthly":
        start = ref_date.replace(day=1)
        last_day = calendar.monthrange(ref_date.year, ref_date.month)[1]
        end = ref_date.replace(day=last_day)
        return start, end

    # weekly: ISO week (Mon-Sun)
    start = ref_date - timedelta(days=ref_date.weekday())
    end = start + timedelta(days=6)
    return start, end


def get_period_label(period: str, start: date, end: date) -> str:
    """Human-readable period label like '2026-W08 (2月16日 - 2月22日)'."""
    if period == "monthly":
        return f"{start.strftime('%Y-%m')} ({start.month}月)"
    iso_year, iso_week, _ = start.isocalendar()
    return (
        f"{iso_year}-W{iso_week:02d} "
        f"({start.month}月{start.day}日 - {end.month}月{end.day}日)"
    )
```

**Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_digest.py -v`
Expected: All 6 tests PASS

**Step 5: Commit**

```bash
git add src/ti/digest.py tests/test_digest.py
git commit -m "feat(digest): add date range utilities for weekly/monthly periods"
```

---

### Task 2: Query and Group Tweets by Category

**Files:**

- Modify: `src/ti/digest.py`
- Modify: `tests/test_digest.py`

**Step 1: Write failing tests for tweet querying and grouping**

Add to `tests/test_digest.py`:

```python
import json
import sqlite3
import pytest
from ti.db import init_db, rebuild_fts
from ti.sync import sync_file

# Reuse the TWEETS fixture pattern from test_search.py
DIGEST_TWEETS = [
    {
        "id": "100", "module": "likes", "created_at": "2026-02-18 10:00:00",
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
        "id": "200", "module": "likes", "created_at": "2026-02-19 10:00:00",
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
        "id": "300", "module": "likes", "created_at": "2026-02-20 10:00:00",
        "full_text": "Another Claude Code workflow tip",
        "media": [], "screen_name": "charlie", "name": "Charlie",
        "profile_image_url": "", "user_id": "u3",
        "in_reply_to": "", "retweeted_status": "", "quoted_status": "",
        "media_tags": [], "tags": [], "module_sort_indices": {},
        "favorite_count": 50, "retweet_count": 5, "bookmark_count": 30,
        "quote_count": 1, "reply_count": 2, "views_count": 5000,
        "favorited": True, "retweeted": False, "bookmarked": False,
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
    # Classify tweets 100 and 300 as claude-code-workflow
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
    # Classify tweet 200 as mcp
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
    tweets = query_tweets_in_range(
        digest_db, "2026-02-16", "2026-02-22"
    )
    assert len(tweets) == 3
    assert all(t["screen_name"] for t in tweets)


def test_query_tweets_excludes_out_of_range(digest_db):
    from ti.digest import query_tweets_in_range
    tweets = query_tweets_in_range(
        digest_db, "2026-03-01", "2026-03-07"
    )
    assert len(tweets) == 0


def test_group_by_category(digest_db):
    from ti.digest import query_tweets_in_range, group_by_category
    tweets = query_tweets_in_range(
        digest_db, "2026-02-16", "2026-02-22"
    )
    groups = group_by_category(tweets)
    assert "claude-code" in groups
    assert "tools-and-ecosystem" in groups
    assert len(groups["claude-code"]) == 2  # tweets 100, 300
    assert len(groups["tools-and-ecosystem"]) == 1  # tweet 200 (mcp)


def test_group_sorted_by_engagement(digest_db):
    from ti.digest import query_tweets_in_range, group_by_category
    tweets = query_tweets_in_range(
        digest_db, "2026-02-16", "2026-02-22"
    )
    groups = group_by_category(tweets)
    cc_tweets = groups["claude-code"]
    # tweet 100 (100 likes + 50 bookmarks) > tweet 300 (50 + 30)
    assert cc_tweets[0]["id"] == "100"


def test_unclassified_detection(digest_db):
    from ti.digest import query_tweets_in_range
    # Remove classification from tweet 300
    digest_db.execute(
        "UPDATE tweets SET primary_tag=NULL, summary=NULL WHERE id='300'"
    )
    digest_db.commit()
    tweets = query_tweets_in_range(
        digest_db, "2026-02-16", "2026-02-22"
    )
    unclassified = [t for t in tweets if t["primary_tag"] is None]
    assert len(unclassified) == 1
    assert unclassified[0]["id"] == "300"
```

**Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_digest.py::test_query_tweets_in_range -v`
Expected: FAIL — `ImportError: cannot import name 'query_tweets_in_range'`

**Step 3: Implement query and grouping functions**

Append to `src/ti/digest.py`:

```python
import sqlite3
from ti.taxonomy import ALL_TAGS


def query_tweets_in_range(
    conn: sqlite3.Connection, start_date: str, end_date: str
) -> list[dict]:
    """Query all tweets within a date range (inclusive), joined with user info."""
    rows = conn.execute(
        """SELECT t.*, u.screen_name, u.name
           FROM tweets t
           JOIN users u ON t.user_id = u.user_id
           WHERE date(t.created_at) >= date(?) AND date(t.created_at) <= date(?)
           ORDER BY t.created_at DESC""",
        (start_date, end_date),
    ).fetchall()
    return [dict(r) for r in rows]


def group_by_category(tweets: list[dict]) -> dict[str, list[dict]]:
    """Group classified tweets by their tag's category, sorted by engagement."""
    groups: dict[str, list[dict]] = {}
    for t in tweets:
        tag = t.get("primary_tag")
        if not tag:
            continue
        category = ALL_TAGS.get(tag)
        if not category:
            continue
        groups.setdefault(category, []).append(t)

    # Sort each group by engagement (likes + bookmarks) descending
    for cat in groups:
        groups[cat].sort(
            key=lambda t: (t.get("favorite_count", 0) + t.get("bookmark_count", 0)),
            reverse=True,
        )
    return groups
```

**Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_digest.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/ti/digest.py tests/test_digest.py
git commit -m "feat(digest): add tweet querying by date range and category grouping"
```

---

### Task 3: AI Prompt Builder and Response Parser

**Files:**

- Modify: `src/ti/digest.py`
- Modify: `tests/test_digest.py`

**Step 1: Write failing tests for prompt building and response parsing**

Add to `tests/test_digest.py`:

````python
def test_build_digest_prompt():
    from ti.digest import build_digest_prompt
    groups = {
        "claude-code": [
            {"id": "100", "screen_name": "alice", "summary": "CC workflow tip",
             "primary_tag": "claude-code-workflow"},
            {"id": "300", "screen_name": "charlie", "summary": "Another CC tip",
             "primary_tag": "claude-code-workflow"},
        ],
        "tools-and-ecosystem": [
            {"id": "200", "screen_name": "bob", "summary": "MCP best practices",
             "primary_tag": "mcp"},
        ],
    }
    prompt = build_digest_prompt(groups, "2026-W08")
    assert "ADHD" in prompt
    assert "claude-code" in prompt
    assert "CC workflow tip" in prompt
    assert "JSON" in prompt


def test_parse_digest_response_valid():
    from ti.digest import parse_digest_response
    raw = '''{
        "tldr": "Big week for CC",
        "topics": [
            {
                "category": "claude-code",
                "headline": "CC is hot",
                "commentary": "Everyone is talking about it",
                "must_read": ["100"],
                "vibe": "hot"
            }
        ],
        "hot_take": "AI is eating the world"
    }'''
    result = parse_digest_response(raw)
    assert result["tldr"] == "Big week for CC"
    assert len(result["topics"]) == 1
    assert result["topics"][0]["vibe"] == "hot"
    assert result["hot_take"] == "AI is eating the world"


def test_parse_digest_response_from_markdown():
    from ti.digest import parse_digest_response
    raw = '''Here is the digest:
```json
{
    "tldr": "Test",
    "topics": [],
    "hot_take": null
}
````

'''
result = parse_digest_response(raw)
assert result["tldr"] == "Test"

def test_parse_digest_response_invalid():
from ti.digest import parse_digest_response
with pytest.raises(ValueError):
parse_digest_response("not json at all")

````

**Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_digest.py::test_build_digest_prompt -v`
Expected: FAIL — `ImportError: cannot import name 'build_digest_prompt'`

**Step 3: Implement prompt builder and response parser**

Append to `src/ti/digest.py`:

```python
import json
import re

# Category display names
CATEGORY_LABELS = {
    "claude-code": "Claude Code",
    "agent-engineering": "Agent Engineering",
    "llm-models": "LLM Models",
    "vibe-coding": "Vibe Coding",
    "tools-and-ecosystem": "Tools & Ecosystem",
    "specific-products": "Specific Products",
    "meta-and-noise": "Meta & Noise",
}


def build_digest_prompt(groups: dict[str, list[dict]], period: str) -> str:
    """Build the AI prompt for digest commentary generation."""
    topics_input = {}
    for category, tweets in groups.items():
        topics_input[category] = [
            {
                "id": t["id"],
                "author": f"@{t['screen_name']}",
                "summary": t.get("summary", t.get("full_text", "")[:100]),
                "tag": t.get("primary_tag", ""),
            }
            for t in tweets
        ]

    input_json = json.dumps(
        {"period": period, "topics": topics_input},
        ensure_ascii=False,
        indent=2,
    )

    return f"""You are writing a weekly digest for a developer who bookmarks lots of tweets but never reads them.

Your reader is heavy ADHD, high-IQ. You MUST hook their attention. Be sharp, opinionated, funny. Draw unexpected connections between tweets. If something is boring, say so and move on.

Write in Chinese. English technical terms are fine.

Here are the tweets grouped by topic, with their AI-generated summaries:

{input_json}

Output a JSON object with this exact structure:

```json
{{
  "tldr": "一句话抓住本周最值得关注的趋势或洞察 — 这是 hook，必须让人想继续读",
  "topics": [
    {{
      "category": "category-key from input",
      "headline": "比分类名更吸引人的一句话标题",
      "commentary": "有态度的分析，不要'本周有N条推文'这种废话。要有观点、有联系、有洞察。可以调侃。",
      "must_read": ["tweet_id_1"],
      "vibe": "hot"
    }}
  ],
  "hot_take": "看完所有推文后的一个犀利观点，跨主题的洞察。可以是反直觉的、挑衅的、或者genuinely insightful的。"
}}
````

Rules:

- `vibe`: "hot" (lots of activity/debate), "steady" (solid content), "quiet" (few tweets, not much happening)
- `must_read`: tweet IDs that are genuinely worth reading in full. Be selective — max 1-2 per topic.
- If a topic has only boring/routine tweets, set vibe to "quiet" and say so in commentary
- `hot_take` is optional — only include if you have something genuinely interesting to say
- Output ONLY the JSON object, no other text"""

def parse_digest_response(raw: str) -> dict:
"""Parse AI response into structured digest data."""
text = raw.strip()

    # Try direct parse
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "tldr" in data:
            return data
    except json.JSONDecodeError:
        pass

    # Try markdown code block
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            if isinstance(data, dict) and "tldr" in data:
                return data
        except json.JSONDecodeError:
            pass

    # Try finding outermost braces
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            data = json.loads(text[start : end + 1])
            if isinstance(data, dict) and "tldr" in data:
                return data
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse digest response: {text[:200]}")

````

**Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_digest.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/ti/digest.py tests/test_digest.py
git commit -m "feat(digest): add AI prompt builder and response parser"
````

---

### Task 4: Assemble Digest Data Structure

**Files:**

- Modify: `src/ti/digest.py`
- Modify: `tests/test_digest.py`

**Step 1: Write failing test for data assembly**

Add to `tests/test_digest.py`:

```python
def test_assemble_digest_data(digest_db):
    from ti.digest import assemble_digest_data
    # Provide mock AI response instead of calling real AI
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
    # Check tweets are nested under topics
    cc_topic = next(t for t in data["topics"] if t["category"] == "claude-code")
    assert len(cc_topic["tweets"]) == 2
    assert cc_topic["tweets"][0]["must_read"] is True  # tweet 100
    assert cc_topic["tweets"][1]["must_read"] is False  # tweet 300
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_digest.py::test_assemble_digest_data -v`
Expected: FAIL — `ImportError: cannot import name 'assemble_digest_data'`

**Step 3: Implement data assembly**

Append to `src/ti/digest.py`:

```python
from datetime import datetime


def assemble_digest_data(
    conn: sqlite3.Connection,
    period: str,
    start_date: str,
    end_date: str,
    ai_response: dict,
) -> dict:
    """Combine DB tweets + AI commentary into the final data structure for the template."""
    from datetime import date as date_type

    start = date_type.fromisoformat(start_date)
    end = date_type.fromisoformat(end_date)

    tweets = query_tweets_in_range(conn, start_date, end_date)
    groups = group_by_category(tweets)

    # Build must_read lookup from AI response
    must_read_ids: set[str] = set()
    ai_topics_by_cat: dict[str, dict] = {}
    for topic in ai_response.get("topics", []):
        cat = topic.get("category", "")
        ai_topics_by_cat[cat] = topic
        for tid in topic.get("must_read", []):
            must_read_ids.add(str(tid))

    # Unique authors
    author_set = {t["screen_name"] for t in tweets}

    # Assemble topics
    assembled_topics = []
    for category, cat_tweets in groups.items():
        ai_topic = ai_topics_by_cat.get(category, {})
        topic_data = {
            "category": category,
            "category_label": CATEGORY_LABELS.get(category, category),
            "headline": ai_topic.get("headline", CATEGORY_LABELS.get(category, category)),
            "commentary": ai_topic.get("commentary", ""),
            "vibe": ai_topic.get("vibe", "steady"),
            "tweets": [
                {
                    "id": t["id"],
                    "author": f"@{t['screen_name']}",
                    "author_name": t.get("name", ""),
                    "text": t["full_text"][:200],
                    "summary": t.get("summary") or "",
                    "primary_tag": t.get("primary_tag") or "",
                    "url": t.get("url", ""),
                    "created_at": t["created_at"][:10],
                    "must_read": t["id"] in must_read_ids,
                    "engagement": {
                        "likes": t.get("favorite_count", 0),
                        "bookmarks": t.get("bookmark_count", 0),
                        "views": t.get("views_count", 0),
                    },
                }
                for t in cat_tweets
            ],
        }
        assembled_topics.append(topic_data)

    # Sort topics: hot first, then by tweet count
    vibe_order = {"hot": 0, "steady": 1, "quiet": 2}
    assembled_topics.sort(
        key=lambda t: (vibe_order.get(t["vibe"], 1), -len(t["tweets"]))
    )

    return {
        "period": get_period_label(period, start, end).split(" ")[0],
        "period_label": get_period_label(period, start, end),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "stats": {
            "total_tweets": len(tweets),
            "total_authors": len(author_set),
            "date_range": [start_date, end_date],
        },
        "tldr": ai_response.get("tldr", ""),
        "hot_take": ai_response.get("hot_take"),
        "topics": assembled_topics,
    }
```

**Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_digest.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/ti/digest.py tests/test_digest.py
git commit -m "feat(digest): assemble final digest data structure from DB + AI response"
```

---

### Task 5: HTML Template

**Files:**

- Create: `src/ti/templates/digest.html`

**Step 1: Create the templates directory**

Run: `mkdir -p /Volumes/DevWork/homebrew/twitter-insights/src/ti/templates`

**Step 2: Write the HTML template**

Create `src/ti/templates/digest.html` — a self-contained React + Tailwind HTML file. Key requirements:

- React 18 via CDN (`react`, `react-dom`, `babel-standalone`)
- Tailwind CSS via CDN (with dark mode config)
- Data read from `window.__DIGEST_DATA__`
- Dark theme, shadcn-inspired Card/Badge components
- Components: `DigestHeader`, `TldrCard`, `TopicSection`, `TweetCard`, `HotTake`, `StatsFooter`
- Vibe badges: hot = red, steady = blue, quiet = gray
- Must-read tweets get a highlight border/badge
- Tweet cards link to original URL
- Responsive grid: 1 col mobile, 2 col desktop
- The `{{DATA}}` placeholder is where Python injects the JSON

```html
<!DOCTYPE html>
<html lang="zh-CN" class="dark">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Twitter Insights Digest</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
      tailwind.config = {
        darkMode: "class",
        theme: {
          extend: {
            colors: {
              background: "#09090b",
              card: "#18181b",
              border: "#27272a",
              muted: "#a1a1aa",
            },
          },
        },
      };
    </script>
    <script
      crossorigin
      src="https://unpkg.com/react@18/umd/react.production.min.js"
    ></script>
    <script
      crossorigin
      src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"
    ></script>
    <script
      crossorigin
      src="https://unpkg.com/@babel/standalone/babel.min.js"
    ></script>
    <script>
      window.__DIGEST_DATA__ = {{DATA}};
    </script>
  </head>
  <body class="bg-background text-zinc-100 min-h-screen">
    <div id="root"></div>
    <script type="text/babel">
      const { useState } = React;
      const data = window.__DIGEST_DATA__;

      function VibeBadge({ vibe }) {
        const styles = {
          hot: "bg-red-500/20 text-red-400 border-red-500/30",
          steady: "bg-blue-500/20 text-blue-400 border-blue-500/30",
          quiet: "bg-zinc-500/20 text-zinc-400 border-zinc-500/30",
        };
        const icons = { hot: "🔥", steady: "📈", quiet: "🌙" };
        return (
          <span
            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs border ${styles[vibe] || styles.steady}`}
          >
            {icons[vibe]} {vibe}
          </span>
        );
      }

      function TweetCard({ tweet }) {
        return (
          <a
            href={tweet.url}
            target="_blank"
            rel="noopener noreferrer"
            className={`block p-4 rounded-lg border transition-colors hover:border-zinc-500
                     ${tweet.must_read ? "border-amber-500/50 bg-amber-500/5" : "border-border bg-card"}`}
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="font-medium text-sm text-zinc-200">
                  {tweet.author}
                </span>
                {tweet.author_name && (
                  <span className="text-xs text-muted">
                    {tweet.author_name}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                {tweet.must_read && (
                  <span className="text-xs bg-amber-500/20 text-amber-400 border border-amber-500/30 px-2 py-0.5 rounded-full">
                    必看
                  </span>
                )}
                <span className="text-xs text-muted">{tweet.created_at}</span>
              </div>
            </div>
            {tweet.summary && (
              <p className="text-sm text-zinc-300 mb-2">{tweet.summary}</p>
            )}
            <p className="text-xs text-muted line-clamp-3">{tweet.text}</p>
            <div className="flex gap-4 mt-3 text-xs text-muted">
              <span>♥ {tweet.engagement.likes.toLocaleString()}</span>
              <span>🔖 {tweet.engagement.bookmarks.toLocaleString()}</span>
              <span>👁 {tweet.engagement.views.toLocaleString()}</span>
            </div>
          </a>
        );
      }

      function TopicSection({ topic }) {
        return (
          <section className="mb-8">
            <div className="flex items-center gap-3 mb-3">
              <h2 className="text-xl font-bold">{topic.headline}</h2>
              <VibeBadge vibe={topic.vibe} />
              <span className="text-sm text-muted">
                {topic.tweets.length} tweets
              </span>
            </div>
            <p className="text-sm text-zinc-300 mb-4 leading-relaxed">
              {topic.commentary}
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {topic.tweets.map((t) => (
                <TweetCard key={t.id} tweet={t} />
              ))}
            </div>
          </section>
        );
      }

      function App() {
        return (
          <div className="max-w-4xl mx-auto px-4 py-8">
            {/* Header */}
            <header className="mb-8">
              <h1 className="text-3xl font-bold mb-1">
                Twitter Insights Digest
              </h1>
              <p className="text-muted">{data.period_label}</p>
              <div className="flex gap-4 mt-2 text-sm text-muted">
                <span>{data.stats.total_tweets} tweets</span>
                <span>{data.stats.total_authors} authors</span>
              </div>
            </header>

            {/* TL;DR */}
            <div className="p-6 rounded-xl border border-border bg-card mb-8">
              <h2 className="text-sm font-medium text-muted mb-2 uppercase tracking-wide">
                TL;DR
              </h2>
              <p className="text-lg text-zinc-100 leading-relaxed">
                {data.tldr}
              </p>
            </div>

            {/* Topics */}
            {data.topics.map((t) => (
              <TopicSection key={t.category} topic={t} />
            ))}

            {/* Hot Take */}
            {data.hot_take && (
              <div className="p-6 rounded-xl border border-orange-500/30 bg-orange-500/5 mt-8 mb-8">
                <h2 className="text-sm font-medium text-orange-400 mb-2 uppercase tracking-wide">
                  🌶️ Hot Take
                </h2>
                <p className="text-zinc-100 leading-relaxed">{data.hot_take}</p>
              </div>
            )}

            {/* Footer */}
            <footer className="text-center text-xs text-muted mt-12 pb-8">
              Generated by ti digest · {data.generated_at}
            </footer>
          </div>
        );
      }

      ReactDOM.createRoot(document.getElementById("root")).render(<App />);
    </script>
  </body>
</html>
```

**Step 3: Verify template is valid HTML**

Run: `python3 -c "from pathlib import Path; t = Path('src/ti/templates/digest.html').read_text(); assert '{{DATA}}' in t; assert 'ReactDOM' in t; print('Template OK')"`
Expected: `Template OK`

**Step 4: Commit**

```bash
git add src/ti/templates/
git commit -m "feat(digest): add React + Tailwind HTML template with shadcn-inspired dark theme"
```

---

### Task 6: HTML Renderer (Template + Data → File)

**Files:**

- Modify: `src/ti/digest.py`
- Modify: `tests/test_digest.py`

**Step 1: Write failing test for HTML rendering**

Add to `tests/test_digest.py`:

```python
def test_render_html(tmp_path):
    from ti.digest import render_digest_html
    data = {
        "period": "2026-W08",
        "period_label": "2026-W08 (2月16日 - 2月22日)",
        "generated_at": "2026-02-21T21:00:00",
        "stats": {"total_tweets": 3, "total_authors": 2, "date_range": ["2026-02-16", "2026-02-22"]},
        "tldr": "Test digest",
        "hot_take": None,
        "topics": [],
    }
    out_path = tmp_path / "digest.html"
    render_digest_html(data, out_path)
    content = out_path.read_text()
    assert "Test digest" in content
    assert "ReactDOM" in content
    assert "{{DATA}}" not in content  # placeholder must be replaced
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_digest.py::test_render_html -v`
Expected: FAIL — `ImportError: cannot import name 'render_digest_html'`

**Step 3: Implement HTML renderer**

Append to `src/ti/digest.py`:

```python
from pathlib import Path

TEMPLATE_PATH = Path(__file__).parent / "templates" / "digest.html"


def render_digest_html(data: dict, output_path: Path) -> None:
    """Inject digest data into HTML template and write to output_path."""
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    data_json = json.dumps(data, ensure_ascii=False)
    html = template.replace("{{DATA}}", data_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
```

**Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_digest.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/ti/digest.py tests/test_digest.py
git commit -m "feat(digest): add HTML renderer that injects data into template"
```

---

### Task 7: AI Call via Codebridge

**Files:**

- Modify: `src/ti/digest.py`
- Modify: `tests/test_digest.py`

This task wires the AI call through codebridge, reusing the pattern from `src/ti/classify.py`.

**Step 1: Write test for AI integration (mocked)**

Add to `tests/test_digest.py`:

```python
from unittest.mock import patch


def test_generate_ai_commentary_calls_codebridge(digest_db):
    from ti.digest import generate_ai_commentary, query_tweets_in_range, group_by_category

    tweets = query_tweets_in_range(digest_db, "2026-02-16", "2026-02-22")
    groups = group_by_category(tweets)

    mock_result = {
        "summary": json.dumps({
            "tldr": "Mocked TL;DR",
            "topics": [{"category": "claude-code", "headline": "Test", "commentary": "Test", "must_read": [], "vibe": "hot"}],
            "hot_take": "Mocked hot take",
        }),
        "run_id": "test-run",
        "output_path": None,
    }

    with patch("ti.digest._run_codebridge", return_value=mock_result) as mock_cb:
        result = generate_ai_commentary(groups, "2026-W08", engine="kimi-code", model="")
        assert result["tldr"] == "Mocked TL;DR"
        mock_cb.assert_called_once()
        # Verify the prompt was passed correctly
        call_args = mock_cb.call_args
        assert "ADHD" in call_args[0][0]
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_digest.py::test_generate_ai_commentary_calls_codebridge -v`
Expected: FAIL — `ImportError: cannot import name 'generate_ai_commentary'`

**Step 3: Implement AI call function**

Append to `src/ti/digest.py` (reuse `_run_codebridge` from classify.py — import it):

```python
from ti.classify import _run_codebridge


def generate_ai_commentary(
    groups: dict[str, list[dict]],
    period_label: str,
    engine: str = "kimi-code",
    model: str = "",
) -> dict:
    """Call AI via codebridge to generate digest commentary."""
    prompt = build_digest_prompt(groups, period_label)
    result = _run_codebridge(prompt, engine=engine, model=model)

    # Prefer full output.txt when available (codebridge >= 0.1.3)
    output_text = None
    run_id = result.get("run_id", "")
    if run_id and result.get("output_path"):
        output_file = Path(__file__).resolve().parent.parent.parent / ".runs" / run_id / result["output_path"]
        if output_file.exists():
            output_text = output_file.read_text()
    if not output_text:
        output_text = result.get("summary", "")

    return parse_digest_response(output_text)
```

**Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_digest.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/ti/digest.py tests/test_digest.py
git commit -m "feat(digest): add AI commentary generation via codebridge"
```

---

### Task 8: CLI Command

**Files:**

- Modify: `src/ti/cli.py`
- Modify: `tests/test_digest.py`

**Step 1: Write failing test for CLI command (dry-run mode)**

Add to `tests/test_digest.py`:

```python
from typer.testing import CliRunner
from ti.cli import app

runner = CliRunner()


def test_cli_digest_dry_run(digest_db, monkeypatch):
    """Dry run should show tweet count without calling AI."""
    monkeypatch.setattr("ti.cli._get_db", lambda: digest_db)
    result = runner.invoke(app, ["digest", "--dry-run"])
    assert result.exit_code == 0
    assert "3" in result.output  # 3 tweets in range


def test_cli_digest_json_format(digest_db, monkeypatch):
    """JSON format should output valid JSON without calling AI or opening browser."""
    from unittest.mock import patch as mock_patch

    monkeypatch.setattr("ti.cli._get_db", lambda: digest_db)

    mock_ai = {
        "tldr": "Test",
        "topics": [],
        "hot_take": None,
    }
    with mock_patch("ti.digest.generate_ai_commentary", return_value=mock_ai):
        result = runner.invoke(app, ["digest", "--format", "json"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "tldr" in parsed
        assert "topics" in parsed
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_digest.py::test_cli_digest_dry_run -v`
Expected: FAIL — `No such command 'digest'`

**Step 3: Implement CLI command**

Add to `src/ti/cli.py` after the `classify` command:

```python
@app.command()
def digest(
    period: str = typer.Option("weekly", "--period", "-p", help="Period: weekly or monthly"),
    format: OutputFormat = _opt_format(),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be digested"),
    no_open: bool = typer.Option(False, "--no-open", help="Don't open browser"),
    save: bool = typer.Option(False, "--save", help="Save to digests/ directory"),
    engine: str = typer.Option("kimi-code", "--engine", "-e", help="codebridge engine"),
    model: str = typer.Option("", "--model", "-m", help="Model name (engine-specific)"),
):
    """Generate a visual digest of recent tweets with AI commentary."""
    from datetime import date
    from ti.digest import (
        get_period_range,
        get_period_label,
        query_tweets_in_range,
        group_by_category,
        generate_ai_commentary,
        assemble_digest_data,
        render_digest_html,
    )

    conn = _get_db()

    start, end = get_period_range(period)
    start_str = start.isoformat()
    end_str = end.isoformat()
    label = get_period_label(period, start, end)

    tweets = query_tweets_in_range(conn, start_str, end_str)

    if not tweets:
        console.print(f"[dim]No tweets found for {label}[/dim]")
        conn.close()
        raise typer.Exit()

    # Check for unclassified tweets
    unclassified = [t for t in tweets if t.get("primary_tag") is None]
    if unclassified:
        console.print(
            f"[yellow]{len(unclassified)} unclassified tweets found. "
            f"Running classification first...[/yellow]"
        )
        from ti.classify import get_unclassified, classify_batch
        from ti.db import rebuild_fts

        uc_tweets = get_unclassified(conn)
        # Filter to only those in our date range
        uc_ids = {t["id"] for t in unclassified}
        uc_in_range = [t for t in uc_tweets if t["id"] in uc_ids]

        if uc_in_range:
            result = classify_batch(conn, uc_in_range, engine=engine, model=model)
            rebuild_fts(conn)
            console.print(
                f"  [green]Classified {result.get('classified', 0)}[/green], "
                f"[red]errors: {result.get('errors', 0)}[/red]"
            )
            # Re-query to get updated data
            tweets = query_tweets_in_range(conn, start_str, end_str)

    groups = group_by_category(tweets)

    if not groups:
        console.print(f"[dim]No classified tweets for {label}[/dim]")
        conn.close()
        raise typer.Exit()

    classified_count = sum(len(v) for v in groups.values())

    if dry_run:
        console.print(f"[bold]{label}[/bold]: {len(tweets)} tweets ({classified_count} classified)")
        for cat, cat_tweets in groups.items():
            console.print(f"  {cat}: {len(cat_tweets)} tweets")
        conn.close()
        return

    # Generate AI commentary
    console.print(f"[cyan]Generating digest for {label}...[/cyan]")
    ai_response = generate_ai_commentary(groups, label, engine=engine, model=model)

    # Assemble data
    data = assemble_digest_data(conn, period, start_str, end_str, ai_response)
    conn.close()

    # JSON format — just output and return
    if format == OutputFormat.JSON:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    # Render HTML
    import tempfile
    period_slug = data["period"]
    tmp_path = Path(tempfile.gettempdir()) / f"ti-digest-{period_slug}.html"
    render_digest_html(data, tmp_path)

    console.print(f"[green]Digest generated:[/green] {tmp_path}")

    # Save copy if requested
    if save:
        save_dir = Path.cwd() / "digests"
        save_path = save_dir / f"{period_slug}.html"
        render_digest_html(data, save_path)
        console.print(f"[green]Saved to:[/green] {save_path}")

    # Open in browser
    if not no_open:
        import subprocess
        subprocess.run(["open", str(tmp_path)], check=False)
```

**Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_digest.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/ti/cli.py tests/test_digest.py
git commit -m "feat(digest): add ti digest CLI command with dry-run, JSON, HTML output"
```

---

### Task 9: Integration Smoke Test

**Files:**

- Modify: `tests/test_digest.py`

**Step 1: Write end-to-end test (mocked AI)**

Add to `tests/test_digest.py`:

```python
def test_end_to_end_digest_html(digest_db, tmp_path, monkeypatch):
    """Full pipeline: query → group → mock AI → assemble → render HTML."""
    from ti.digest import (
        query_tweets_in_range,
        group_by_category,
        assemble_digest_data,
        render_digest_html,
    )

    tweets = query_tweets_in_range(digest_db, "2026-02-16", "2026-02-22")
    assert len(tweets) == 3

    groups = group_by_category(tweets)
    assert len(groups) >= 2

    ai_response = {
        "tldr": "本周 Claude Code 和 MCP 都很火",
        "topics": [
            {
                "category": "claude-code",
                "headline": "CC 社区在讨论工作流优化",
                "commentary": "有意思的是 alice 和 charlie 都在聊这个话题",
                "must_read": ["100"],
                "vibe": "hot",
            },
            {
                "category": "tools-and-ecosystem",
                "headline": "MCP 最佳实践",
                "commentary": "bob 分享了 MCP 的最佳实践",
                "must_read": [],
                "vibe": "steady",
            },
        ],
        "hot_take": "CC + MCP 正在重新定义开发者工具链",
    }

    data = assemble_digest_data(
        digest_db, "weekly", "2026-02-16", "2026-02-22", ai_response
    )

    # Verify data structure
    assert data["stats"]["total_tweets"] == 3
    assert len(data["topics"]) == 2
    assert data["hot_take"] == "CC + MCP 正在重新定义开发者工具链"

    # Render HTML
    out = tmp_path / "test-digest.html"
    render_digest_html(data, out)
    html = out.read_text()

    # Check key content is in rendered HTML
    assert "本周 Claude Code 和 MCP 都很火" in html
    assert "CC 社区在讨论工作流优化" in html
    assert "ReactDOM" in html
    assert "{{DATA}}" not in html
```

**Step 2: Run test**

Run: `python3 -m pytest tests/test_digest.py::test_end_to_end_digest_html -v`
Expected: PASS

**Step 3: Run all tests**

Run: `python3 -m pytest tests/ -v`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add tests/test_digest.py
git commit -m "test(digest): add end-to-end integration smoke test"
```

---

### Task 10: Visual Verification via AI Vision

**Satisfies BDD scenario:** "Visual appearance of the digest page"

This task generates a realistic sample digest HTML, screenshots it, and uses AI vision to verify it meets the visual acceptance criteria.

**Files:**

- Create: `tests/visual/generate_sample.py` (one-time script, not a pytest test)

**Step 1: Create sample data generator**

Create `tests/visual/generate_sample.py` — a script that generates a realistic digest HTML with mock data (no AI call needed). This produces a file rich enough to visually verify all UI elements.

```python
"""Generate a sample digest HTML for visual verification."""
import json
import sys
sys.path.insert(0, "src")

from pathlib import Path
from ti.digest import render_digest_html

SAMPLE_DATA = {
    "period": "2026-W08",
    "period_label": "2026-W08 (2月16日 - 2月22日)",
    "generated_at": "2026-02-21T21:30:00",
    "stats": {
        "total_tweets": 42,
        "total_authors": 28,
        "date_range": ["2026-02-16", "2026-02-22"],
    },
    "tldr": "本周最大的新闻是 Claude Code 4.5 发布后社区的疯狂实验——从 CLAUDE.md 最佳实践到多 agent 协作流水线，CC 生态正在以肉眼可见的速度成熟。与此同时，MCP 悄悄成为了事实上的 agent-tool 协议标准。",
    "hot_take": "看完这周 42 条推文，一个强烈的感觉：我们正在见证 '开发者工具' 和 'AI agent' 这两个品类的合并。CC 不再是 IDE 的附属品，它正在变成开发者的 operating system。三个月后回看这周，可能是个转折点。",
    "topics": [
        {
            "category": "claude-code",
            "category_label": "Claude Code",
            "headline": "CC 社区在疯狂试验 CLAUDE.md 的极限",
            "commentary": "这周 CC 生态爆发了。@dotey 分享了他的 10 万字 CLAUDE.md，社区炸了——有人说这是 prompt engineering 的终极形态，有人说这是在用自然语言写代码。@karpathy 则从另一个角度切入，讨论了 CC 在大型 monorepo 中的工作流。有意思的是两人得出了完全相反的结论：dotey 认为 CLAUDE.md 越详细越好，karpathy 觉得应该保持精简让 AI 自己探索。",
            "vibe": "hot",
            "tweets": [
                {
                    "id": "t001", "author": "@dotey", "author_name": "宝玉",
                    "text": "分享一下我的 CLAUDE.md 最佳实践。经过三个月的迭代，我发现最重要的是把你的工作流程写清楚，而不是写一堆规则...",
                    "summary": "Detailed CLAUDE.md best practices after 3 months of iteration",
                    "primary_tag": "claude-code-workflow", "url": "https://x.com/dotey/status/t001",
                    "created_at": "2026-02-18", "must_read": True,
                    "engagement": {"likes": 342, "bookmarks": 188, "views": 52000},
                },
                {
                    "id": "t002", "author": "@karpathy", "author_name": "Andrej Karpathy",
                    "text": "I've been using Claude Code on a large monorepo and here's what I learned: keep your CLAUDE.md minimal...",
                    "summary": "Minimal CLAUDE.md approach works better for large monorepos",
                    "primary_tag": "claude-code-workflow", "url": "https://x.com/karpathy/status/t002",
                    "created_at": "2026-02-19", "must_read": True,
                    "engagement": {"likes": 1205, "bookmarks": 567, "views": 180000},
                },
                {
                    "id": "t003", "author": "@swyx", "author_name": "swyx",
                    "text": "CC skills are basically composable prompt modules. This changes everything about how we think about developer tooling...",
                    "summary": "CC skills as composable prompt modules represent a paradigm shift",
                    "primary_tag": "claude-code-skills", "url": "https://x.com/swyx/status/t003",
                    "created_at": "2026-02-20", "must_read": False,
                    "engagement": {"likes": 89, "bookmarks": 45, "views": 12000},
                },
            ],
        },
        {
            "category": "agent-engineering",
            "category_label": "Agent Engineering",
            "headline": "多 Agent 编排从玩具走向生产",
            "commentary": "本周 agent 领域最值得关注的是从 demo 到 production 的过渡。几个实际的多 agent 部署案例出现了，不再是 toy example。@AndrewNg 分享的 agent 设计模式总结特别值得读——他把现有的模式归纳成了四类。",
            "vibe": "steady",
            "tweets": [
                {
                    "id": "t004", "author": "@AndrewNg", "author_name": "Andrew Ng",
                    "text": "Four design patterns for AI agents that actually work in production...",
                    "summary": "Four production-ready AI agent design patterns",
                    "primary_tag": "multi-agent-orchestration", "url": "https://x.com/AndrewNg/status/t004",
                    "created_at": "2026-02-17", "must_read": True,
                    "engagement": {"likes": 2100, "bookmarks": 890, "views": 350000},
                },
                {
                    "id": "t005", "author": "@langaborkedev", "author_name": "LangChain Dev",
                    "text": "我们在生产环境中部署了一个 5-agent 的协作系统，处理客服工单。分享一下踩过的坑...",
                    "summary": "Production deployment lessons from a 5-agent customer service system",
                    "primary_tag": "multi-agent-orchestration", "url": "https://x.com/langaborkedev/status/t005",
                    "created_at": "2026-02-19", "must_read": False,
                    "engagement": {"likes": 156, "bookmarks": 78, "views": 25000},
                },
            ],
        },
        {
            "category": "tools-and-ecosystem",
            "category_label": "Tools & Ecosystem",
            "headline": "MCP 悄悄变成了事实标准",
            "commentary": "没有大新闻，但看趋势很明显：越来越多的工具开始原生支持 MCP。本周又有三个主流 IDE 宣布集成。量变快到质变了。",
            "vibe": "steady",
            "tweets": [
                {
                    "id": "t006", "author": "@alexalbert__", "author_name": "Alex Albert",
                    "text": "MCP adoption is accelerating. This week: VS Code, IntelliJ, and Neovim all shipped MCP support...",
                    "summary": "Three major IDEs shipped MCP support in the same week",
                    "primary_tag": "mcp", "url": "https://x.com/alexalbert__/status/t006",
                    "created_at": "2026-02-20", "must_read": False,
                    "engagement": {"likes": 445, "bookmarks": 210, "views": 78000},
                },
            ],
        },
        {
            "category": "meta-and-noise",
            "category_label": "Meta & Noise",
            "headline": "本周闲聊区",
            "commentary": "几条行业八卦和生活推文，没什么特别值得深入的。",
            "vibe": "quiet",
            "tweets": [
                {
                    "id": "t007", "author": "@random_dev", "author_name": "Random Dev",
                    "text": "今天摸鱼看到一个有趣的 GitHub repo...",
                    "summary": "Random interesting GitHub discovery",
                    "primary_tag": "offbeat", "url": "https://x.com/random_dev/status/t007",
                    "created_at": "2026-02-21", "must_read": False,
                    "engagement": {"likes": 12, "bookmarks": 3, "views": 800},
                },
            ],
        },
    ],
}


if __name__ == "__main__":
    out = Path("/tmp/ti-digest-sample.html")
    render_digest_html(SAMPLE_DATA, out)
    print(f"Sample digest written to {out}")
```

**Step 2: Generate sample HTML**

Run: `python3 tests/visual/generate_sample.py`
Expected: `/tmp/ti-digest-sample.html` created.

**Step 3: Screenshot with Playwright**

Run: `python3 -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1280, 'height': 900})
    page.goto('file:///tmp/ti-digest-sample.html')
    page.wait_for_timeout(3000)  # wait for Tailwind CDN + React render
    page.screenshot(path='/tmp/ti-digest-screenshot.png', full_page=True)
    browser.close()
    print('Screenshot saved to /tmp/ti-digest-screenshot.png')
"`

If Playwright is not installed: `pip install playwright && playwright install chromium`

**Step 4: AI visual verification**

Use the Read tool to view `/tmp/ti-digest-screenshot.png` and verify against the BDD "Visual appearance" scenario checklist:

- [ ] Dark theme background (near-black, #09090b)
- [ ] TL;DR card at top, prominent, readable
- [ ] Topic sections with headline, vibe badge (🔥/📈/🌙), tweet count
- [ ] Commentary text under each headline
- [ ] Tweet cards in a grid (2 columns on desktop)
- [ ] Tweet cards show: author, summary, text preview, engagement stats
- [ ] Must-read tweets have golden/amber highlight border + "必看" badge
- [ ] Hot Take section at bottom with orange accent
- [ ] Footer with generation timestamp
- [ ] Chinese text renders correctly
- [ ] Overall aesthetic: clean, readable, "I want to keep reading" vibe

Alternatively, delegate to codebridge/opencode with Gemini for a second opinion:

```bash
codebridge submit --engine opencode --message "Review this screenshot of a digest page. Check: dark theme, card layout, vibe badges, must-read highlights, responsive grid, Chinese text. Report any visual issues." --file /tmp/ti-digest-screenshot.png --wait
```

**Step 5: Fix any visual issues and re-verify**

Iterate on `src/ti/templates/digest.html` until the visual checklist passes.

**Step 6: Run full end-to-end with real data**

Run: `ti digest --dry-run` (verify tweet counts)
Run: `ti digest` (full generation with real AI)

**Step 7: Final commit**

```bash
git add -A
git commit -m "feat(digest): complete ti digest with visual verification"
```
