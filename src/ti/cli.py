import typer

app = typer.Typer(
    name="ti",
    help="Twitter Insights - search and browse curated tweet knowledge base",
    no_args_is_help=True,
    invoke_without_command=True,
)


@app.callback()
def main():
    """Twitter Insights - search and browse curated tweet knowledge base."""


@app.command()
def stats():
    """Show database statistics."""
    typer.echo("ti is working")


if __name__ == "__main__":
    app()
