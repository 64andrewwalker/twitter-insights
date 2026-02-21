# Twitter Insights (`ti`)

CLI tool for searching curated Twitter insights. SQLite + FTS5 backend with AI classification.

## Quick Start

```bash
# Import tweets
ti sync twitter-tweets-*.json

# Search
ti search "Claude Code"
ti search "MCP" --format json --sort popular

# Browse
ti latest 10
ti author dotey
ti tag claude-code-workflow
ti tags

# Show single tweet
ti show <tweet_id>

# Classify unclassified tweets (uses codebridge + Haiku)
ti classify --dry-run
ti classify --batch-size 15

# Stats
ti stats
```

## For Agents

All commands support `--format json` for structured output:

```bash
ti search "how to optimize MCP server" --format json --limit 5
ti tag agent-engineering --format json
ti author karpathy --format json
```

JSON envelope: `{ command, total, returned, offset, results: [...] }`

## Project Structure

- `src/ti/` — Python package (Typer CLI)
- `ti.db` — SQLite database (gitignored)
- `twitter-tweets-*.json` — Raw data files (gitignored)

## Key Files

- `src/ti/cli.py` — CLI commands
- `src/ti/db.py` — Schema, FTS5 trigram
- `src/ti/search.py` — Query functions
- `src/ti/classify.py` — codebridge + Haiku classification
- `src/ti/taxonomy.py` — 32 tags in 7 categories
- `src/ti/output.py` — JSON/human/brief formatting

## Development

```bash
pip install -e .
python3 -m pytest tests/ -v
```

## Data Snapshot

- Latest sync: 2026-02-21
- Latest tweet ID: `2025033171864354981`
- Tweets: 340, Authors: 202
- Date range: 2025-08-28 to 2026-02-21
