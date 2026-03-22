"""Output formatting: human (Rich), JSON envelope, brief."""

import json
from enum import Enum

from rich.console import Console
from rich.panel import Panel


class OutputFormat(str, Enum):
    HUMAN = "human"
    JSON = "json"
    BRIEF = "brief"


def _row_to_result(row: dict) -> dict:
    tags_str = row.get("tags", "")
    tags = [t for t in tags_str.split(",") if t] if isinstance(tags_str, str) else []
    return {
        "id": row["id"],
        "author": f"@{row['screen_name']}",
        "author_name": row.get("name", ""),
        "created_at": row["created_at"],
        "text": row["full_text"],
        "summary": row.get("summary"),
        "url": row.get("url", ""),
        "tags": tags,
        "primary_tag": row.get("primary_tag"),
        "confidence": row.get("confidence"),
        "engagement": {
            "likes": row.get("favorite_count", 0),
            "bookmarks": row.get("bookmark_count", 0),
            "views": row.get("views_count", 0),
        },
    }


def format_results(
    command: str,
    results: list[dict],
    total: int,
    fmt: OutputFormat = OutputFormat.HUMAN,
    query: str | None = None,
    offset: int = 0,
) -> str:
    if fmt == OutputFormat.JSON:
        envelope = {
            "command": command,
            "total": total,
            "returned": len(results),
            "offset": offset,
            "results": [_row_to_result(r) for r in results],
        }
        if query is not None:
            envelope["query"] = query
        return json.dumps(envelope, ensure_ascii=False, indent=2)

    if fmt == OutputFormat.BRIEF:
        lines = []
        for r in results:
            tag = r.get("primary_tag", "?")
            lines.append(
                f"[{tag}] {r['id']} @{r['screen_name']} " f"{r['full_text'][:80]}..."
            )
        if total > len(results) + offset:
            lines.append(f"\n({total} total, showing {offset+1}-{offset+len(results)})")
        return "\n".join(lines)

    # Human format with Rich
    console = Console(width=100, force_terminal=False)
    with console.capture() as capture:
        for r in results:
            tag = r.get("primary_tag", "unclassified")
            conf = r.get("confidence")
            conf_str = f" ({conf:.0%})" if conf else ""
            header = f"@{r['screen_name']} · {r['created_at'][:10]} · [{tag}{conf_str}]"

            text = r["full_text"]
            if len(text) > 300:
                text = text[:300] + "..."

            summary = r.get("summary")
            body = f"{text}\n"
            if summary:
                body += f"\n> {summary}\n"
            body += (
                f"\nLikes: {r.get('favorite_count',0):,}  "
                f"Bookmarks: {r.get('bookmark_count',0):,}  "
                f"Views: {r.get('views_count',0):,}  "
                f"Link: {r.get('url','')}"
            )

            console.print(Panel(body, title=header, border_style="dim"))

        if total > len(results) + offset:
            console.print(
                f"\nShowing {offset+1}-{offset+len(results)} of {total}. "
                f"Use --offset {offset+len(results)} to see more.",
                style="dim",
            )

    return capture.get()


def format_stats(stats: dict, fmt: OutputFormat = OutputFormat.HUMAN) -> str:
    """Format database stats for output."""
    if fmt == OutputFormat.JSON:
        envelope = {
            "command": "stats",
            "total_tweets": stats["total_tweets"],
            "classified": stats["classified"],
            "unclassified": stats["unclassified"],
            "authors": stats["authors"],
            "date_range": {
                "from": stats.get("date_range_from", ""),
                "to": stats.get("date_range_to", ""),
            },
            "latest_tweet_id": stats.get("latest_tweet_id", ""),
        }
        return json.dumps(envelope, ensure_ascii=False, indent=2)

    if fmt == OutputFormat.BRIEF:
        lines = [
            f"tweets: {stats['total_tweets']} ({stats['classified']} classified, {stats['unclassified']} pending)",
            f"authors: {stats['authors']}",
        ]
        if stats.get("date_range_from"):
            lines.append(
                f"range: {stats['date_range_from']} -> {stats['date_range_to']}"
            )
        return "\n".join(lines)

    # Human format
    console = Console(width=100, force_terminal=False)
    with console.capture() as capture:
        console.print("[bold]Twitter Insights Database[/bold]")
        console.print(
            f"  Tweets: {stats['total_tweets']} "
            f"({stats['classified']} classified, {stats['unclassified']} pending)"
        )
        console.print(f"  Authors: {stats['authors']}")
        if stats.get("date_range_from"):
            console.print(
                f"  Date range: {stats['date_range_from']} -> {stats['date_range_to']}"
            )
        if stats.get("latest_tweet_id"):
            console.print(f"  Latest tweet ID: {stats['latest_tweet_id']}")
    return capture.get()


def format_tags(tag_list: list[dict], fmt: OutputFormat = OutputFormat.HUMAN) -> str:
    """Format tag list for output."""
    if fmt == OutputFormat.JSON:
        envelope = {
            "command": "tags",
            "total": len(tag_list),
            "results": tag_list,
        }
        return json.dumps(envelope, ensure_ascii=False, indent=2)

    if fmt == OutputFormat.BRIEF:
        lines = []
        for t in tag_list:
            if t["count"] > 0:
                lines.append(f"{t['name']}: {t['count']}")
        return "\n".join(lines)

    # Human format
    from rich.table import Table

    console = Console(width=100, force_terminal=False)
    with console.capture() as capture:
        table = Table(title="Tags", show_lines=False)
        table.add_column("Category", style="cyan")
        table.add_column("Tag", style="bold")
        table.add_column("Tweets", justify="right")
        for t in tag_list:
            table.add_row(t["category"], t["name"], str(t["count"]))
        console.print(table)
    return capture.get()


def format_remote_results(
    command: str, data: dict, fmt: OutputFormat = OutputFormat.HUMAN
) -> str:
    """Format server JSON response for human/brief output. Results are already transformed."""
    if fmt == OutputFormat.JSON:
        return json.dumps(data, ensure_ascii=False, indent=2)

    results = data.get("results", [])
    total = data.get("total", len(results))
    offset = data.get("offset", 0)
    query = data.get("query")

    if fmt == OutputFormat.BRIEF:
        lines = []
        for r in results:
            tag = r.get("primary_tag", "?")
            text = r.get("text", "")[:80]
            lines.append(f"[{tag}] {r.get('id', '')} {r.get('author', '')} {text}...")
        if total > len(results) + offset:
            lines.append(
                f"\n({total} total, showing {offset + 1}-{offset + len(results)})"
            )
        return "\n".join(lines)

    # Human format
    console = Console(width=100, force_terminal=False)
    with console.capture() as capture:
        for r in results:
            tag = r.get("primary_tag", "unclassified")
            header = f"{r.get('author', '')} · {r.get('created_at', '')[:10]} · [{tag}]"
            text = r.get("text", "")
            if len(text) > 300:
                text = text[:300] + "..."
            eng = r.get("engagement", {})
            body = (
                f"{text}\n"
                f"\nLikes: {eng.get('likes', 0):,}  "
                f"Bookmarks: {eng.get('bookmarks', 0):,}  "
                f"Views: {eng.get('views', 0):,}  "
                f"Link: {r.get('url', '')}"
            )
            console.print(Panel(body, title=header, border_style="dim"))
        if total > len(results) + offset:
            console.print(
                f"\nShowing {offset + 1}-{offset + len(results)} of {total}. "
                f"Use --offset {offset + len(results)} to see more.",
                style="dim",
            )
    return capture.get()
