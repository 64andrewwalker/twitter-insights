import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from ti.db import get_connection, init_db
from ti.output import OutputFormat, format_results

app = typer.Typer(
    name="ti",
    help="Twitter Insights - search and browse curated tweet knowledge base",
    no_args_is_help=True,
    invoke_without_command=True,
)
console = Console()

# Common option factories for consistent --format/--limit/--offset on every command
_opt_format = lambda: typer.Option(OutputFormat.HUMAN, "--format", "-f", help="Output format")
_opt_limit = lambda: typer.Option(20, "--limit", "-l", help="Max results")
_opt_offset = lambda: typer.Option(0, "--offset", help="Skip N results")


@app.callback()
def main():
    pass


def _get_db():
    conn = get_connection()
    init_db(conn)
    return conn


def _print_output(output: str, fmt: OutputFormat):
    """Print formatted output appropriately for the format type."""
    if fmt in (OutputFormat.JSON, OutputFormat.BRIEF):
        print(output)
    else:
        console.print(output, highlight=False)


@app.command()
def sync(
    file: Path = typer.Argument(None, help="Path to Twitter JSON export file"),
    dir: Path = typer.Option(None, "--dir", "-d", help="Import all *.json files from directory"),
):
    """Import tweets from a JSON export file or directory."""
    from ti.sync import sync_file

    if dir is not None:
        if not dir.is_dir():
            console.print(f"[red]Not a directory: {dir}[/red]")
            raise typer.Exit(1)
        files = sorted(dir.glob("*.json"))
        if not files:
            console.print(f"[dim]No JSON files found in {dir}[/dim]")
            return
        conn = _get_db()
        total_inserted = 0
        total_updated = 0
        for f in files:
            result = sync_file(conn, f)
            total_inserted += result["inserted"]
            total_updated += result["updated"]
            console.print(
                f"  {f.name}: {result['inserted']} new, {result['updated']} updated"
            )
        conn.close()
        console.print(
            f"[green]Total:[/green] {total_inserted} new, {total_updated} updated "
            f"from {len(files)} files"
        )
        return

    if file is None:
        console.print("[red]Provide a file path or use --dir[/red]")
        raise typer.Exit(1)

    if not file.exists():
        console.print(f"[red]File not found: {file}[/red]")
        raise typer.Exit(1)

    conn = _get_db()
    result = sync_file(conn, file)
    conn.close()

    console.print(
        f"[green]Synced {file.name}:[/green] "
        f"{result['inserted']} new, {result['updated']} updated "
        f"({result['duration_ms']}ms)"
    )


@app.command()
def stats():
    """Show database statistics."""
    conn = _get_db()
    total = conn.execute("SELECT COUNT(*) FROM tweets").fetchone()[0]
    users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    classified = conn.execute(
        "SELECT COUNT(*) FROM tweets WHERE primary_tag IS NOT NULL"
    ).fetchone()[0]
    unclassified = total - classified

    dates = conn.execute(
        "SELECT MIN(created_at), MAX(created_at) FROM tweets"
    ).fetchone()

    latest_row = conn.execute(
        "SELECT value FROM metadata WHERE key='latest_tweet_id'"
    ).fetchone()

    console.print("[bold]Twitter Insights Database[/bold]")
    console.print(f"  Tweets: {total} ({classified} classified, {unclassified} pending)")
    console.print(f"  Authors: {users}")
    if dates[0]:
        console.print(f"  Date range: {dates[0]} -> {dates[1]}")
    if latest_row:
        console.print(f"  Latest tweet ID: {latest_row[0]}")
    conn.close()


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    sort: str = typer.Option("relevant", help="Sort: relevant|recent|popular"),
    format: OutputFormat = _opt_format(),
    limit: int = _opt_limit(),
    offset: int = _opt_offset(),
):
    """Full-text search across all tweets."""
    from ti.search import fts_search

    conn = _get_db()
    results, total = fts_search(conn, query, limit=limit, offset=offset, sort=sort)
    conn.close()

    if not results:
        console.print(f"[dim]No results for '{query}'[/dim]")
        raise typer.Exit()

    output = format_results(
        command="search", results=results, total=total,
        fmt=format, query=query, offset=offset,
    )
    _print_output(output, format)


@app.command()
def tag(
    name: str = typer.Argument(..., help="Tag name to filter by"),
    format: OutputFormat = _opt_format(),
    limit: int = _opt_limit(),
    offset: int = _opt_offset(),
):
    """Filter tweets by tag name."""
    from ti.search import by_tag

    conn = _get_db()
    results, total = by_tag(conn, name, limit=limit, offset=offset)
    conn.close()

    if not results:
        console.print(f"[dim]No tweets with tag '{name}'[/dim]")
        raise typer.Exit()

    output = format_results(
        command="tag", results=results, total=total,
        fmt=format, query=name, offset=offset,
    )
    _print_output(output, format)


@app.command()
def tags(
    format: OutputFormat = _opt_format(),
):
    """List all tags with tweet counts."""
    from ti.search import list_tags

    conn = _get_db()
    tag_list = list_tags(conn)
    conn.close()

    if format == OutputFormat.JSON:
        print(json.dumps({"command": "tags", "results": tag_list}, indent=2))
        return

    if format == OutputFormat.BRIEF:
        for t in tag_list:
            if t["count"] > 0:
                print(f"{t['name']}: {t['count']}")
        return

    # Human format
    table = Table(title="Tags", show_lines=False)
    table.add_column("Category", style="cyan")
    table.add_column("Tag", style="bold")
    table.add_column("Tweets", justify="right")

    for t in tag_list:
        table.add_row(t["category"], t["name"], str(t["count"]))

    console.print(table)


@app.command()
def author(
    handle: str = typer.Argument(..., help="Author screen name (with or without @)"),
    format: OutputFormat = _opt_format(),
    limit: int = _opt_limit(),
    offset: int = _opt_offset(),
):
    """Filter tweets by author handle."""
    from ti.search import by_author

    conn = _get_db()
    results, total = by_author(conn, handle, limit=limit, offset=offset)
    conn.close()

    if not results:
        console.print(f"[dim]No tweets by @{handle.lstrip('@')}[/dim]")
        raise typer.Exit()

    output = format_results(
        command="author", results=results, total=total,
        fmt=format, query=handle.lstrip("@"), offset=offset,
    )
    _print_output(output, format)


@app.command()
def show(
    tweet_id: str = typer.Argument(..., help="Tweet ID to display"),
    format: OutputFormat = _opt_format(),
):
    """Show a single tweet in full detail."""
    from ti.search import show_tweet

    conn = _get_db()
    result = show_tweet(conn, tweet_id)
    conn.close()

    if not result:
        console.print(f"[red]Tweet {tweet_id} not found[/red]")
        raise typer.Exit(1)

    output = format_results(
        command="show", results=[result], total=1, fmt=format,
    )
    _print_output(output, format)


@app.command()
def latest(
    n: int = typer.Argument(20, help="Number of tweets"),
    format: OutputFormat = _opt_format(),
    offset: int = _opt_offset(),
):
    """Show the most recent tweets."""
    from ti.search import latest_tweets

    conn = _get_db()
    results, total = latest_tweets(conn, limit=n, offset=offset)
    conn.close()

    if not results:
        console.print("[dim]No tweets found[/dim]")
        raise typer.Exit()

    output = format_results(
        command="latest", results=results, total=total,
        fmt=format, offset=offset,
    )
    _print_output(output, format)


@app.command()
def classify(
    batch_size: int = typer.Option(15, "--batch-size", "-b", help="Tweets per batch"),
    retry_failed: bool = typer.Option(False, "--retry", help="Retry failed classifications"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be classified"),
):
    """Classify unclassified tweets using AI (codebridge + Haiku)."""
    from ti.classify import get_unclassified, classify_batch
    from ti.db import rebuild_fts

    conn = _get_db()
    tweets = get_unclassified(conn, retry_failed=retry_failed)

    if not tweets:
        console.print("[green]All tweets are classified![/green]")
        conn.close()
        return

    if dry_run:
        console.print(f"[bold]{len(tweets)} tweets to classify[/bold]")
        for t in tweets[:5]:
            console.print(f"  {t['id']} @{t['screen_name']}: {t['full_text'][:60]}...")
        if len(tweets) > 5:
            console.print(f"  ... and {len(tweets) - 5} more")
        conn.close()
        return

    console.print(f"[bold]Classifying {len(tweets)} tweets in batches of {batch_size}...[/bold]")

    total_classified = 0
    total_errors = 0

    for i in range(0, len(tweets), batch_size):
        batch = tweets[i:i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(tweets) + batch_size - 1) // batch_size

        console.print(f"\n[cyan]Batch {batch_num}/{total_batches}[/cyan] ({len(batch)} tweets)")

        result = classify_batch(conn, batch)
        total_classified += result.get("classified", 0)
        total_errors += result.get("errors", 0)

        if "error" in result:
            console.print(f"  [red]Error: {result['error'][:100]}[/red]")
        else:
            console.print(
                f"  [green]Classified: {result['classified']}[/green]"
                f"  [red]Errors: {result['errors']}[/red]"
            )

    # Rebuild FTS after all batches
    rebuild_fts(conn)

    console.print(f"\n[bold green]Done![/bold green] {total_classified} classified, {total_errors} errors")
    conn.close()


if __name__ == "__main__":
    app()
