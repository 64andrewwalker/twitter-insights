"""Classification pipeline: dispatch codebridge + Haiku for tweet tagging."""

import json
import subprocess
import sqlite3
from pathlib import Path

from ti.taxonomy import TAXONOMY, ALL_TAGS

PROJECT_DIR = str(Path(__file__).resolve().parent.parent.parent)

GLOSSARY = """
Chinese tech slang glossary:
- cc / CC = Claude Code
- 龙虾 = OpenClaw (lobster logo)
- 反代 = reverse proxy
- 内卷 = competitive pressure / rat race
- 赛博 = cyber/digital
- 技能栈 = skills stack
- 牛马 = overworked workers (ironic)
- 模型 = AI model
- 提示词 = prompt
- 智能体 = AI agent
- 工作流 = workflow
- 上下文 = context (window)
"""


def _build_taxonomy_text() -> str:
    lines = []
    for category, tags in TAXONOMY.items():
        lines.append(f"\n## Category: {category}")
        for tag_name, description in tags.items():
            lines.append(f"  - `{tag_name}`: {description}")
    return "\n".join(lines)


def _build_prompt(tweets: list[dict]) -> str:
    taxonomy_text = _build_taxonomy_text()

    tweets_json = json.dumps(
        [{"id": t["id"], "text": t["full_text"], "author": t["screen_name"]}
         for t in tweets],
        ensure_ascii=False,
        indent=2,
    )

    return f"""You are a tweet classifier. Classify each tweet into the tag taxonomy below.

## Tag Taxonomy
{taxonomy_text}

{GLOSSARY}

## Tweets to Classify

{tweets_json}

## Instructions

For each tweet, output a JSON array with one object per tweet:

```json
[
  {{
    "id": "tweet_id",
    "primary_tag": "most-relevant-tag",
    "tags": ["primary-tag", "optional-second-tag"],
    "confidence": 0.85,
    "summary": "One line summary of the tweet's insight",
    "lang": "zh"
  }}
]
```

Rules:
- `primary_tag` must be exactly one tag name from the taxonomy above
- `tags` array: 1-3 tags, always includes primary_tag as first element
- `confidence`: 0.0-1.0 how confident you are in the primary_tag classification
- `summary`: One concise sentence capturing the tweet's key insight (in English)
- `lang`: "zh" for Chinese, "en" for English, "mixed" for both, "ja" for Japanese
- If a tweet is off-topic (personal life, health tips, etc.), use tag "offbeat"
- Output ONLY the JSON array, no other text"""


def _run_codebridge(prompt: str) -> dict:
    """Submit classification task to codebridge and return result."""
    result = subprocess.run(
        [
            "codebridge", "submit",
            "--engine", "claude-code",
            "--model", "haiku",
            "--workspace", PROJECT_DIR,
            "--intent", "ops",
            "--message", prompt,
            "--wait",
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )

    if result.returncode != 0:
        raise RuntimeError(f"codebridge failed: {result.stderr}")

    return json.loads(result.stdout)


def _parse_classifications(summary: str) -> list[dict]:
    """Extract JSON classification array from codebridge summary."""
    import re

    # The summary might contain markdown code blocks or extra text
    # Try to find JSON array in the text
    text = summary.strip()

    # Try direct parse first
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass

    # Try to extract from markdown code block
    match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass

    # Try to find array brackets
    start = text.find('[')
    end = text.rfind(']')
    if start != -1 and end != -1:
        try:
            data = json.loads(text[start:end + 1])
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse classifications from: {text[:200]}")


def _apply_classifications(conn: sqlite3.Connection, classifications: list[dict]) -> tuple[int, int]:
    """Write classification results to DB. Returns (success_count, error_count)."""
    success = 0
    errors = 0

    for c in classifications:
        tweet_id = c.get("id")
        primary_tag = c.get("primary_tag", "")
        tags = c.get("tags", [])
        confidence = c.get("confidence", 0.0)
        summary = c.get("summary", "")
        lang = c.get("lang")

        # Validate primary_tag exists in taxonomy
        if primary_tag not in ALL_TAGS:
            conn.execute(
                "UPDATE tweets SET classification_error = ? WHERE id = ?",
                (f"Unknown tag: {primary_tag}", tweet_id),
            )
            errors += 1
            continue

        # Update tweet
        conn.execute(
            """UPDATE tweets SET
                 primary_tag = ?, confidence = ?, summary = ?, lang = ?,
                 classification_error = NULL, updated_at = datetime('now')
               WHERE id = ?""",
            (primary_tag, confidence, summary, lang, tweet_id),
        )

        # Insert tweet_tags
        for tag_name in tags:
            if tag_name in ALL_TAGS:
                tag_row = conn.execute(
                    "SELECT id FROM tags WHERE name = ?", (tag_name,)
                ).fetchone()
                if tag_row:
                    conn.execute(
                        "INSERT OR IGNORE INTO tweet_tags (tweet_id, tag_id) VALUES (?, ?)",
                        (tweet_id, tag_row[0]),
                    )

        success += 1

    conn.commit()
    return success, errors


def get_unclassified(conn: sqlite3.Connection, retry_failed: bool = False) -> list[dict]:
    """Get tweets that need classification."""
    if retry_failed:
        rows = conn.execute(
            """SELECT t.id, t.full_text, u.screen_name
               FROM tweets t JOIN users u ON t.user_id = u.user_id
               WHERE t.primary_tag IS NULL AND t.classification_error IS NOT NULL
               ORDER BY t.created_at"""
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT t.id, t.full_text, u.screen_name
               FROM tweets t JOIN users u ON t.user_id = u.user_id
               WHERE t.primary_tag IS NULL AND t.classification_error IS NULL
               ORDER BY t.created_at"""
        ).fetchall()
    return [dict(r) for r in rows]


def classify_batch(
    conn: sqlite3.Connection,
    tweets: list[dict],
    dry_run: bool = False,
) -> dict:
    """Classify a batch of tweets. Returns stats dict."""
    if dry_run:
        return {"batch_size": len(tweets), "dry_run": True}

    prompt = _build_prompt(tweets)

    try:
        result = _run_codebridge(prompt)
        summary = result.get("summary", "")
        classifications = _parse_classifications(summary)
        success, errors = _apply_classifications(conn, classifications)
        return {
            "batch_size": len(tweets),
            "classified": success,
            "errors": errors,
            "run_id": result.get("run_id"),
        }
    except Exception as e:
        # Mark all tweets in batch with error
        for tweet in tweets:
            conn.execute(
                "UPDATE tweets SET classification_error = ? WHERE id = ?",
                (str(e), tweet["id"]),
            )
        conn.commit()
        return {
            "batch_size": len(tweets),
            "classified": 0,
            "errors": len(tweets),
            "error": str(e),
        }
