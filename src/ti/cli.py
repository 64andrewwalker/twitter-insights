import json
from pathlib import Path

import click
import typer
from rich.console import Console
from ti.config import (
    load_config,
    resolve_db_path,
    save_config,
    mask_api_key,
    _VALID_KEYS,
    _VALID_MODES,
)
from ti.db import get_connection, init_db
from ti.output import OutputFormat, format_results

app = typer.Typer(
    name="ti",
    help="Twitter Insights - search and browse curated tweet knowledge base",
    no_args_is_help=True,
    invoke_without_command=True,
)
console = Console()

# Subcommand groups
config_app = typer.Typer(
    name="config", help="Manage ti configuration", no_args_is_help=True
)
db_app = typer.Typer(name="db", help="Database management", no_args_is_help=True)
app.add_typer(config_app)
app.add_typer(db_app)

# Common option factories for consistent --format/--limit/--offset on every command
_opt_format = lambda: typer.Option(
    OutputFormat.HUMAN, "--format", "-f", help="Output format"
)
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


def _is_remote() -> bool:
    cfg = load_config()
    return cfg.get("mode") == "remote"


def _get_remote_client():
    from ti.remote import RemoteClient

    cfg = load_config()
    api_url = cfg.get("api_url", "")
    api_key = cfg.get("api_key", "")
    if not api_url or not api_key:
        console.print(
            "[red]Remote mode requires api_url and api_key. Run: ti config set api_url/api_key[/red]"
        )
        raise typer.Exit(1)
    return RemoteClient(api_url, api_key)


def _local_only(command_name: str):
    if _is_remote():
        console.print(
            f"[red]{command_name} is local-only. Switch mode: ti config set mode local[/red]"
        )
        raise typer.Exit(1)


@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="Config key (mode, api_url, api_key, db_path)"),
    value: str = typer.Argument(..., help="Config value"),
):
    """Set a configuration value."""
    if key not in _VALID_KEYS:
        console.print(
            f"[red]Invalid key: {key}. Valid: {', '.join(sorted(_VALID_KEYS))}[/red]"
        )
        raise typer.Exit(1)
    if key == "mode" and value not in _VALID_MODES:
        console.print(
            f"[red]Invalid mode: {value}. Valid: {', '.join(sorted(_VALID_MODES))}[/red]"
        )
        raise typer.Exit(1)

    cfg = load_config()
    cfg[key] = value if value != "null" else None
    save_config(cfg)
    display = mask_api_key(value) if key == "api_key" else value
    console.print(f"[green]{key}[/green] = {display}")


@config_app.command("show")
def config_show():
    """Show current configuration."""
    cfg = load_config()
    for k, v in cfg.items():
        display = mask_api_key(v) if k == "api_key" and v else v
        console.print(f"  {k}: {display}")


@db_app.command("push")
def db_push(
    force: bool = typer.Option(
        False, "--force", help="Force push even if remote is newer"
    ),
):
    """Push local database to remote server."""
    import sys

    from ti.config import resolve_db_path
    from ti.push import push_db

    cfg = load_config()
    if not cfg.get("api_url") or not cfg.get("api_key"):
        console.print(
            "[red]Configure remote first: ti config set api_url/api_key[/red]"
        )
        raise typer.Exit(1)

    db_path = resolve_db_path()
    if not db_path.exists():
        console.print(f"[red]Database not found: {db_path}[/red]")
        raise typer.Exit(1)

    try:
        result = push_db(db_path, cfg["api_url"], cfg["api_key"], force=force)
        print(json.dumps(result, indent=2), file=sys.stderr)
    except Exception as e:
        console.print(f"[red]Push failed: {e}[/red]", highlight=False)
        raise typer.Exit(1)


@app.command()
def sync(
    file: Path = typer.Argument(None, help="Path to Twitter JSON export file"),
    dir: Path = typer.Option(
        None, "--dir", "-d", help="Import all *.json files from directory"
    ),
):
    """Import tweets from a JSON export file or directory."""
    _local_only("sync")
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
        # Auto-push to remote if configured
        from ti.push import auto_push

        cfg = load_config()
        auto_push(cfg.get("api_url", ""), cfg.get("api_key", ""), resolve_db_path())
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

    # Auto-push to remote if configured
    from ti.push import auto_push

    cfg = load_config()
    auto_push(cfg.get("api_url", ""), cfg.get("api_key", ""), resolve_db_path())

    console.print(
        f"[green]Synced {file.name}:[/green] "
        f"{result['inserted']} new, {result['updated']} updated "
        f"({result['duration_ms']}ms)"
    )


@app.command()
def stats(
    format: OutputFormat = _opt_format(),
):
    """Show database statistics."""
    if _is_remote():
        client = _get_remote_client()
        data = client.stats()
        if format == OutputFormat.JSON:
            print(json.dumps(data, ensure_ascii=False, indent=2))
            return
        stats_data = {
            "total_tweets": data["total_tweets"],
            "classified": data["classified"],
            "unclassified": data["unclassified"],
            "authors": data["authors"],
            "date_range_from": data["date_range"]["from"],
            "date_range_to": data["date_range"]["to"],
            "latest_tweet_id": data.get("latest_tweet_id", ""),
        }
        from ti.output import format_stats

        output = format_stats(stats_data, fmt=format)
        _print_output(output, format)
        return

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
    conn.close()

    stats_data = {
        "total_tweets": total,
        "classified": classified,
        "unclassified": unclassified,
        "authors": users,
        "date_range_from": dates[0] or "",
        "date_range_to": dates[1] or "",
        "latest_tweet_id": latest_row[0] if latest_row else "",
    }

    from ti.output import format_stats

    output = format_stats(stats_data, fmt=format)
    _print_output(output, format)


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    sort: str = typer.Option("relevant", help="Sort: relevant|recent|popular"),
    format: OutputFormat = _opt_format(),
    limit: int = _opt_limit(),
    offset: int = _opt_offset(),
):
    """Full-text search across all tweets."""
    if _is_remote():
        client = _get_remote_client()
        data = client.search(query, sort=sort, limit=limit, offset=offset)
        if format == OutputFormat.JSON:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            from ti.output import format_remote_results

            output = format_remote_results(command="search", data=data, fmt=format)
            _print_output(output, format)
        return

    from ti.search import fts_search

    conn = _get_db()
    results, total = fts_search(conn, query, limit=limit, offset=offset, sort=sort)
    conn.close()

    if not results:
        console.print(f"[dim]No results for '{query}'[/dim]")
        raise typer.Exit()

    output = format_results(
        command="search",
        results=results,
        total=total,
        fmt=format,
        query=query,
        offset=offset,
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
    if _is_remote():
        client = _get_remote_client()
        data = client.tag(name, limit=limit, offset=offset)
        if format == OutputFormat.JSON:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            from ti.output import format_remote_results

            output = format_remote_results(command="tag", data=data, fmt=format)
            _print_output(output, format)
        return

    from ti.search import by_tag

    conn = _get_db()
    results, total = by_tag(conn, name, limit=limit, offset=offset)
    conn.close()

    if not results:
        console.print(f"[dim]No tweets with tag '{name}'[/dim]")
        raise typer.Exit()

    output = format_results(
        command="tag",
        results=results,
        total=total,
        fmt=format,
        query=name,
        offset=offset,
    )
    _print_output(output, format)


@app.command()
def tags(
    format: OutputFormat = _opt_format(),
):
    """List all tags with tweet counts."""
    if _is_remote():
        client = _get_remote_client()
        data = client.tags()
        if format == OutputFormat.JSON:
            print(json.dumps(data, ensure_ascii=False, indent=2))
            return
        from ti.output import format_tags

        output = format_tags(data.get("results", []), fmt=format)
        _print_output(output, format)
        return

    from ti.search import list_tags
    from ti.output import format_tags

    conn = _get_db()
    tag_list = list_tags(conn)
    conn.close()

    output = format_tags(tag_list, fmt=format)
    _print_output(output, format)


@app.command()
def author(
    handle: str = typer.Argument(..., help="Author screen name (with or without @)"),
    format: OutputFormat = _opt_format(),
    limit: int = _opt_limit(),
    offset: int = _opt_offset(),
):
    """Filter tweets by author handle."""
    if _is_remote():
        client = _get_remote_client()
        data = client.author(handle, limit=limit, offset=offset)
        if format == OutputFormat.JSON:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            from ti.output import format_remote_results

            output = format_remote_results(command="author", data=data, fmt=format)
            _print_output(output, format)
        return

    from ti.search import by_author

    conn = _get_db()
    results, total = by_author(conn, handle, limit=limit, offset=offset)
    conn.close()

    if not results:
        console.print(f"[dim]No tweets by @{handle.lstrip('@')}[/dim]")
        raise typer.Exit()

    output = format_results(
        command="author",
        results=results,
        total=total,
        fmt=format,
        query=handle.lstrip("@"),
        offset=offset,
    )
    _print_output(output, format)


@app.command()
def show(
    tweet_id: str = typer.Argument(..., help="Tweet ID to display"),
    format: OutputFormat = _opt_format(),
):
    """Show a single tweet in full detail."""
    if _is_remote():
        client = _get_remote_client()
        data = client.show(tweet_id)
        if format == OutputFormat.JSON:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            from ti.output import format_remote_results

            output = format_remote_results(command="show", data=data, fmt=format)
            _print_output(output, format)
        return

    from ti.search import show_tweet

    conn = _get_db()
    result = show_tweet(conn, tweet_id)
    conn.close()

    if not result:
        console.print(f"[red]Tweet {tweet_id} not found[/red]")
        raise typer.Exit(1)

    output = format_results(
        command="show",
        results=[result],
        total=1,
        fmt=format,
    )
    _print_output(output, format)


@app.command()
def latest(
    n: int = typer.Argument(20, help="Number of tweets"),
    format: OutputFormat = _opt_format(),
    offset: int = _opt_offset(),
):
    """Show the most recent tweets."""
    if _is_remote():
        client = _get_remote_client()
        data = client.latest(n=n, offset=offset)
        if format == OutputFormat.JSON:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            from ti.output import format_remote_results

            output = format_remote_results(command="latest", data=data, fmt=format)
            _print_output(output, format)
        return

    from ti.search import latest_tweets

    conn = _get_db()
    results, total = latest_tweets(conn, limit=n, offset=offset)
    conn.close()

    if not results:
        console.print("[dim]No tweets found[/dim]")
        raise typer.Exit()

    output = format_results(
        command="latest",
        results=results,
        total=total,
        fmt=format,
        offset=offset,
    )
    _print_output(output, format)


@app.command()
def classify(
    batch_size: int = typer.Option(15, "--batch-size", "-b", help="Tweets per batch"),
    retry_failed: bool = typer.Option(
        False, "--retry", help="Retry failed classifications"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be classified"
    ),
    engine: str = typer.Option("kimi-code", "--engine", "-e", help="codebridge engine"),
    model: str = typer.Option("", "--model", "-m", help="Model name (engine-specific)"),
):
    """Classify unclassified tweets using AI via codebridge."""
    _local_only("classify")
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

    console.print(
        f"[bold]Classifying {len(tweets)} tweets in batches of {batch_size} "
        f"(engine={engine}, model={model or 'default'})...[/bold]"
    )

    total_classified = 0
    total_errors = 0

    for i in range(0, len(tweets), batch_size):
        batch = tweets[i : i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(tweets) + batch_size - 1) // batch_size

        console.print(
            f"\n[cyan]Batch {batch_num}/{total_batches}[/cyan] ({len(batch)} tweets)"
        )

        result = classify_batch(conn, batch, engine=engine, model=model)
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

    console.print(
        f"\n[bold green]Done![/bold green] {total_classified} classified, {total_errors} errors"
    )
    conn.close()

    # Auto-push to remote if configured
    from ti.push import auto_push

    cfg = load_config()
    auto_push(cfg.get("api_url", ""), cfg.get("api_key", ""), resolve_db_path())


@app.command()
def digest(
    period: str = typer.Option(
        "weekly",
        "--period",
        "-p",
        help="Period: weekly or monthly",
        click_type=click.Choice(["weekly", "monthly"]),
    ),
    format: OutputFormat = typer.Option(
        "human",
        "--format",
        "-f",
        help="Output format (human or json)",
        click_type=click.Choice(["human", "json"]),
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be digested"
    ),
    no_open: bool = typer.Option(False, "--no-open", help="Don't open browser"),
    save: bool = typer.Option(False, "--save", help="Save to digests/ directory"),
    engine: str = typer.Option("kimi-code", "--engine", "-e", help="codebridge engine"),
    model: str = typer.Option("", "--model", "-m", help="Model name (engine-specific)"),
):
    """Generate a visual digest of recent tweets with AI commentary."""
    _local_only("digest")
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
        uc_ids = {t["id"] for t in unclassified}
        uc_in_range = [t for t in uc_tweets if t["id"] in uc_ids]

        if uc_in_range:
            result = classify_batch(conn, uc_in_range, engine=engine, model=model)
            rebuild_fts(conn)
            console.print(
                f"  [green]Classified {result.get('classified', 0)}[/green], "
                f"[red]errors: {result.get('errors', 0)}[/red]"
            )
            tweets = query_tweets_in_range(conn, start_str, end_str)

    groups = group_by_category(tweets)

    if not groups:
        console.print(f"[dim]No classified tweets for {label}[/dim]")
        conn.close()
        raise typer.Exit()

    classified_count = sum(len(v) for v in groups.values())

    if dry_run:
        console.print(
            f"[bold]{label}[/bold]: {len(tweets)} tweets ({classified_count} classified)"
        )
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

    # JSON format
    if format == OutputFormat.JSON:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    # Render HTML
    import tempfile

    period_slug = data["period"]
    tmp_path = Path(tempfile.gettempdir()) / f"ti-digest-{period_slug}.html"
    render_digest_html(data, tmp_path)

    console.print(f"[green]Digest generated:[/green] {tmp_path}")

    if save:
        save_dir = Path.cwd() / "digests"
        save_path = save_dir / f"{period_slug}.html"
        render_digest_html(data, save_path)
        console.print(f"[green]Saved to:[/green] {save_path}")

    if not no_open:
        import subprocess

        subprocess.run(["open", str(tmp_path)], check=False)


if __name__ == "__main__":
    app()
