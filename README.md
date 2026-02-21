# Twitter Insights (`ti`)

CLI tool for organizing, classifying, and searching curated Twitter/X timeline content. Built for both human browsing and AI agent retrieval.

## Features

- **Full-text search** with FTS5 trigram tokenizer (handles Chinese + English without config)
- **AI classification** via [codebridge](https://github.com/64andrewwalker/codebridge) — supports kimi-code, claude-code, opencode, codex engines
- **32-tag taxonomy** across 7 categories (claude-code, agent-engineering, llm-models, vibe-coding, tools-and-ecosystem, specific-products, meta-and-noise)
- **Agent-friendly** — all commands support `--format json` with consistent envelope
- **Deduplication** — 3-layer dedup (import UPSERT, classification NULL check, watermark tracking)

## Install

```bash
pip install -e .
```

Requires Python 3.12+ and [codebridge](https://github.com/64andrewwalker/codebridge) for AI classification.

## Usage

```bash
# Import tweets from JSON export
ti sync tweets.json
ti sync --dir ./exports/

# Search
ti search "Claude Code"
ti search "MCP server" --sort popular --format json

# Browse by tag / author
ti tag claude-code-workflow
ti author karpathy
ti tags                    # list all tags with counts

# Recent tweets
ti latest 10

# Single tweet detail
ti show <tweet_id>

# AI classification (requires codebridge)
ti classify --dry-run                     # preview
ti classify -b 5                          # kimi-code (default)
ti classify -e claude-code -m haiku       # use Haiku

# Stats
ti stats
```

## Agent Integration

All commands support `--format json` for structured output:

```bash
ti search "how to build MCP servers" --format json --limit 5
```

Returns:

```json
{
  "command": "search",
  "total": 42,
  "returned": 5,
  "offset": 0,
  "results": [
    {
      "id": "...",
      "text": "...",
      "author": "...",
      "primary_tag": "mcp",
      "summary": "...",
      "engagement": { "replies": 0, "retweets": 5, "likes": 23 }
    }
  ]
}
```

## Project Structure

```
src/ti/
  cli.py        — Typer CLI commands
  db.py         — SQLite schema, FTS5 trigram
  parser.py     — Twitter JSON export parser
  sync.py       — Import with UPSERT dedup
  search.py     — FTS, tag, author, latest queries
  classify.py   — AI classification via codebridge
  taxonomy.py   — 32 tags in 7 categories
  output.py     — JSON / human / brief formatters
tests/          — pytest test suite
docs/plans/     — Design docs and implementation plan
```

## Development

```bash
pip install -e .
python3 -m pytest tests/ -v
```

## License

MIT
