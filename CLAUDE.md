# Twitter Insights (`ti`)

CLI tool for searching curated Twitter insights. Dual-mode: local SQLite or remote API at `ti.wongbro.com`.

## Quick Start

### Local mode (default)

```bash
pip install -e .

# Import tweets
ti sync twitter-tweets-*.json

# Search
ti search "Claude Code" --format json --sort popular

# Browse
ti latest 10
ti author dotey
ti tag claude-code-workflow
ti tags
ti stats
```

### Remote mode (for agents — no local DB needed)

```bash
pip install ti-insights
ti config set mode remote
ti config set api_url https://ti.wongbro.com
ti config set api_key <key>
ti search "MCP server" --format json --limit 5
```

## For Agents

All commands support `--format json` for structured output:

```bash
ti search "how to optimize MCP server" --format json --limit 5
ti tag agent-engineering --format json
ti author karpathy --format json
ti stats --format json
ti tags --format json
```

JSON envelope: `{ command, total, returned, offset, results: [...] }`

### Remote mode command matrix

| Command                                        | Remote | Local | Notes                               |
| ---------------------------------------------- | ------ | ----- | ----------------------------------- |
| search, tag, tags, author, show, latest, stats | yes    | yes   | Full parity                         |
| sync, classify, digest                         | no     | yes   | Local only — needs files/codebridge |
| db push                                        | no     | yes   | Pushes local DB to server           |
| db versions, db restore                        | yes    | yes   | Manages R2 backups                  |
| config set/show                                | n/a    | n/a   | Local config management             |

## Project Structure

```
src/ti/
├── cli.py          — CLI commands + remote mode routing
├── config.py       — Config read/write + DB path resolution (env → config → XDG)
├── db.py           — Schema, FTS5 trigram, connection management
├── search.py       — Query functions (FTS, tag, author, latest)
├── output.py       — JSON/human/brief formatting + format_stats/format_tags
├── push.py         — VACUUM INTO snapshot, upload, auto-push subprocess
├── remote.py       — HTTP client for remote mode
├── classify.py     — AI classification via codebridge
├── digest.py       — Weekly/monthly digest generation
├── taxonomy.py     — 32 tags in 7 categories
├── sync.py         — Twitter JSON import with UPSERT
└── templates/      — HTML digest template

server/
├── app.py          — FastAPI application (/v1/ endpoints, rate limiting)
├── auth.py         — API key middleware (timing-safe, key rotation)
├── db.py           — Connection manager + read-write lock
├── validate.py     — Schema validation for pushed DBs
├── r2.py           — Cloudflare R2 archival + backup pruning
├── Dockerfile      — Python 3.12-slim deployment
└── requirements.txt
```

## Key Config

- Config file: `~/.config/ti/config.json` (0600 permissions)
- DB path resolution: `$TI_DB_PATH` env → config `db_path` → `~/.local/share/ti/ti.db`
- No CWD fallback — DB path is stable regardless of working directory
- Proxy toggle: `ti config set proxy none` (bypass) or `system` (default)

## Development

```bash
pip install -e .
pip install -e ".[server]"   # for server development
python3 -m pytest tests/ -v  # 103 unit tests + 14 E2E tests
```

### Server deployment

```bash
# Railway (production)
railway up

# Local dev
uvicorn server.app:create_app --factory --reload
```

### Environment variables (server)

- `TI_API_KEY` — Required, min 32 chars
- `TI_API_KEY_OLD` — Optional, for key rotation
- `R2_ENDPOINT`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET` — R2 backups

## Data Snapshot

- Latest sync: 2026-03-17
- Tweets: 605, Authors: 320, Classified: 604
- Date range: 2024-11-20 to 2026-03-17
- Production: `ti.wongbro.com` (Railway + Cloudflare)
