"""Digest generation: query, group, AI commentary, HTML rendering."""

import calendar
import json
import re
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from ti.taxonomy import ALL_TAGS

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


def get_period_range(period: str, ref_date: date | None = None) -> tuple[date, date]:
    """Return (start, end) dates for the given period containing ref_date."""
    if ref_date is None:
        ref_date = date.today()
    if period not in ("weekly", "monthly"):
        raise ValueError(f"Invalid period: {period}. Must be 'weekly' or 'monthly'.")
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
    """Human-readable period label."""
    if period == "monthly":
        return f"{start.strftime('%Y-%m')} ({start.month}月)"
    iso_year, iso_week, _ = start.isocalendar()
    return f"{iso_year}-W{iso_week:02d} ({start.month}月{start.day}日 - {end.month}月{end.day}日)"


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
    for cat in groups:
        groups[cat].sort(
            key=lambda t: (t.get("favorite_count", 0) + t.get("bookmark_count", 0)),
            reverse=True,
        )
    return groups


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
        {"period": period, "topics": topics_input}, ensure_ascii=False, indent=2
    )

    return f"""You are writing a weekly digest for a developer who bookmarks lots of tweets but never reads them.

Your reader is heavy ADHD, high-IQ. You MUST hook their attention. Be sharp, opinionated, funny. Draw unexpected connections between tweets. If something is boring, say so and move on.

Write in Chinese. English technical terms are fine.

Here are the tweets grouped by topic, with their AI-generated summaries:

{input_json}

Output a JSON object with this exact structure:

```json
{{{{
  "tldr": "一句话抓住本周最值得关注的趋势或洞察",
  "topics": [
    {{{{
      "category": "category-key from input",
      "headline": "比分类名更吸引人的一句话标题",
      "commentary": "有态度的分析",
      "must_read": ["tweet_id_1"],
      "vibe": "hot"
    }}}}
  ],
  "hot_take": "犀利观点"
}}}}
```

Rules:
- `vibe`: "hot" / "steady" / "quiet"
- `must_read`: max 1-2 per topic
- `hot_take` is optional
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
    start_idx = text.find("{")
    end_idx = text.rfind("}")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        try:
            data = json.loads(text[start_idx : end_idx + 1])
            if isinstance(data, dict) and "tldr" in data:
                return data
        except json.JSONDecodeError:
            pass
    raise ValueError(f"Could not parse digest response: {text[:200]}")


def assemble_digest_data(
    conn: sqlite3.Connection,
    period: str,
    start_date: str,
    end_date: str,
    ai_response: dict,
) -> dict:
    """Combine DB tweets + AI commentary into the final data structure for the template."""
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    tweets = query_tweets_in_range(conn, start_date, end_date)
    groups = group_by_category(tweets)

    must_read_ids: set[str] = set()
    ai_topics_by_cat: dict[str, dict] = {}
    for topic in ai_response.get("topics", []):
        cat = topic.get("category", "")
        ai_topics_by_cat[cat] = topic
        for tid in topic.get("must_read", []):
            must_read_ids.add(str(tid))

    author_set = {t["screen_name"] for t in tweets}

    assembled_topics = []
    for category, cat_tweets in groups.items():
        ai_topic = ai_topics_by_cat.get(category, {})
        topic_data = {
            "category": category,
            "category_label": CATEGORY_LABELS.get(category, category),
            "headline": ai_topic.get(
                "headline", CATEGORY_LABELS.get(category, category)
            ),
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


def generate_ai_commentary(
    groups: dict[str, list[dict]],
    period_label: str,
    engine: str = "kimi-code",
    model: str = "",
) -> dict:
    """Call AI via codebridge to generate digest commentary."""
    from ti.classify import _run_codebridge

    prompt = build_digest_prompt(groups, period_label)
    result = _run_codebridge(prompt, engine=engine, model=model)

    # Prefer full output.txt when available (codebridge >= 0.1.3)
    output_text = None
    run_id = result.get("run_id", "")
    if run_id and result.get("output_path"):
        output_file = (
            Path(__file__).resolve().parent.parent.parent
            / ".runs"
            / run_id
            / result["output_path"]
        )
        if output_file.exists():
            output_text = output_file.read_text()
    if not output_text:
        output_text = result.get("summary", "")

    return parse_digest_response(output_text)


TEMPLATE_PATH = Path(__file__).parent / "templates" / "digest.html"


def render_digest_html(data: dict, output_path: Path) -> None:
    """Inject digest data into HTML template and write to output_path."""
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    data_json = json.dumps(data, ensure_ascii=False)
    # Prevent </script> in tweet text from breaking the inline script block
    data_json = data_json.replace("</", "<\\/")
    html = template.replace("{{DATA}}", data_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
