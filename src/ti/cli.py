import typer
from pathlib import Path
from rich.console import Console
from ti.db import get_connection, init_db

app = typer.Typer(
    name="ti",
    help="Twitter Insights - search and browse curated tweet knowledge base",
    no_args_is_help=True,
    invoke_without_command=True,
)
console = Console()


@app.callback()
def main():
    pass


def _get_db():
    conn = get_connection()
    init_db(conn)
    return conn


@app.command()
def sync(
    file: Path = typer.Argument(..., help="Path to Twitter JSON export file"),
):
    """Import tweets from a JSON export file."""
    if not file.exists():
        console.print(f"[red]File not found: {file}[/red]")
        raise typer.Exit(1)

    from ti.sync import sync_file

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

    latest = conn.execute(
        "SELECT value FROM metadata WHERE key='latest_tweet_id'"
    ).fetchone()

    console.print(f"[bold]Twitter Insights Database[/bold]")
    console.print(f"  Tweets: {total} ({classified} classified, {unclassified} pending)")
    console.print(f"  Authors: {users}")
    if dates[0]:
        console.print(f"  Date range: {dates[0]} → {dates[1]}")
    if latest:
        console.print(f"  Latest tweet ID: {latest[0]}")
    conn.close()


if __name__ == "__main__":
    app()
