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
                f"[{tag}] {r['id']} @{r['screen_name']} "
                f"{r['full_text'][:80]}..."
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
