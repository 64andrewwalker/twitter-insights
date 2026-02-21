# Twitter Insights CLI (`ti`) Design Document

**Date:** 2026-02-21
**Status:** Approved

## Overview

A CLI tool that turns curated Twitter likes into a searchable, categorized knowledge base. Serves both humans (browsable, readable output) and AI agents (structured JSON output via bash calls).

## Architecture

```
ti CLI (Python + SQLite)
├── ti sync <file>        → Import JSON, deduplicate, UPSERT engagement
├── ti classify           → Dispatch codebridge + Haiku for AI tagging
├── ti search <query>     → FTS5 full-text search
├── ti ask <question>     → Haiku query expansion → FTS search
├── ti tag <name>         → Filter by tag
├── ti tags               → List all tags with counts
├── ti author <handle>    → Filter by author
├── ti show <id>          → Show single tweet detail
├── ti latest [n]         → Show latest n tweets
├── ti stats              → Statistics overview

codebridge (classification engine)
├── codebridge submit --engine claude-code --model haiku --wait
├── Batch classification: 10-20 tweets per request
└── Daemon mode: --max-concurrent 4 for parallel classification
```

## Data Model (SQLite)

### `users` table
| Column | Type | Notes |
|---|---|---|
| user_id | TEXT PK | Twitter stable user ID |
| screen_name | TEXT | Latest known handle (mutable) |
| name | TEXT | Display name |
| profile_image_url | TEXT | Avatar |
| updated_at | TEXT | ISO 8601 |

### `tweets` table
| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | Tweet snowflake ID |
| created_at | TEXT | ISO 8601 UTC |
| full_text | TEXT | Full tweet content |
| summary | TEXT | Haiku-generated one-line summary |
| lang | TEXT | zh/en/mixed/ja |
| user_id | TEXT FK → users | Author |
| url | TEXT | Tweet URL |
| favorite_count | INT | |
| retweet_count | INT | |
| bookmark_count | INT | |
| quote_count | INT | |
| reply_count | INT | |
| views_count | INT | |
| quoted_tweet_id | TEXT | Quoted tweet relation |
| conversation_id | TEXT | Thread grouping |
| media_json | TEXT | JSON array of media objects |
| module | TEXT | likes/bookmarks |
| primary_tag | TEXT | Most relevant tag |
| confidence | REAL | Classification confidence 0.0-1.0 |
| classification_error | TEXT | Error message if classification failed |
| source_file | TEXT | Source filename for auditing |
| imported_at | TEXT | ISO 8601 |
| updated_at | TEXT | ISO 8601, set on UPSERT |

### `tags` table
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| name | TEXT UNIQUE | Lowercase, e.g. "claude-code-workflow" |
| category | TEXT | Lowercase, e.g. "claude-code" |

### `tweet_tags` table
| Column | Type | Notes |
|---|---|---|
| tweet_id | TEXT FK → tweets | |
| tag_id | INTEGER FK → tags | |
| PRIMARY KEY | (tweet_id, tag_id) | |

### `import_log` table
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| imported_at | TEXT | ISO 8601 |
| source_file | TEXT | Basename of file |
| file_size_bytes | INT | For detecting re-imports |
| tweets_inserted | INT | |
| tweets_updated | INT | |
| tweets_classified | INT | |
| classification_errors | INT | |
| duration_ms | INT | |

### `metadata` table
| Column | Type | Notes |
|---|---|---|
| key | TEXT PK | |
| value | TEXT | |

Keys: `latest_tweet_id`, `latest_tweet_date`, `last_sync_time`, `total_classified`

### FTS5 Virtual Table
```sql
CREATE VIRTUAL TABLE tweets_fts USING fts5(
  full_text,
  summary,
  content='tweets',
  content_rowid='rowid',
  tokenize='trigram'
);
```
Trigram tokenizer handles both Chinese (no word boundaries) and English text without configuration.

### Indexes
```sql
CREATE INDEX idx_tweets_user_id ON tweets(user_id);
CREATE INDEX idx_tweets_created_at ON tweets(created_at);
CREATE INDEX idx_tweets_module ON tweets(module);
CREATE INDEX idx_tweets_primary_tag ON tweets(primary_tag);
CREATE INDEX idx_tweets_unclassified ON tweets(id) WHERE primary_tag IS NULL;
CREATE INDEX idx_tweet_tags_tag_id ON tweet_tags(tag_id);
CREATE INDEX idx_tweet_tags_reverse ON tweet_tags(tag_id, tweet_id);
```

## Tag Taxonomy (7 categories, 32 tags)

### claude-code
- `claude-code-workflow` — Usage patterns, session management, context strategies, CLAUDE.md
- `claude-code-skills` — Skills/SKILL.md, skill repos, Context7, Vercel skills
- `claude-code-hooks` — Hooks, plugins, pre/post hooks
- `claude-code-memory` — Memory persistence, context carryover
- `claude-code-tools` — Third-party tools, wrappers, IDEs integrating CC

### agent-engineering
- `multi-agent-orchestration` — Multi-agent setups, sub-agents, orchestrator patterns
- `agent-memory` — Agent memory architecture, persistent memory systems
- `agent-autonomy` — Autonomous agents, always-on assistants
- `agent-browser` — Browser automation for agents
- `agent-sdk` — Agent SDKs, programmatic agent construction

### llm-models
- `model-comparison` — Side-by-side rankings, benchmarks
- `model-release` — New model announcements
- `api-access` — API pricing, proxies, subscription strategies
- `local-models` — Local inference, GPU selection, VRAM

### vibe-coding
- `vibe-coding-workflow` — AI-assisted dev process
- `vibe-coding-ui` — AI-generated frontend, design tools
- `vibe-coding-philosophy` — Opinions on AI coding quality, future of SE

### tools-and-ecosystem
- `mcp` — Model Context Protocol servers, setup
- `prompt-engineering` — System prompt design, CLAUDE.md optimization
- `open-source` — Open-source project highlights
- `devtools` — Non-AI dev tooling (tmux, monorepo, GitHub Actions)
- `ai-product-design` — AI-native product design philosophy

### specific-products
- `cursor` — Cursor IDE
- `openclaw` — OpenClaw/Clawdbot/MoltBot/NanoClaw
- `opencode` — Opencode, Oh My OpenCode
- `gemini-ecosystem` — Gemini CLI, Google AI, Chrome integration
- `codex` — OpenAI Codex CLI, AGENTS.md
- `kimi` — Kimi/Moonshot AI models

### meta-and-noise
- `ai-industry` — Industry news, layoffs, enterprise AI
- `learning-resources` — Reading lists, paper summaries, podcast recs
- `offbeat` — Personal life, health tips, off-topic

## Deduplication (3-layer)

### Layer 1: Import dedup (`ti sync`)
```sql
INSERT INTO tweets (id, ...) VALUES (?, ...)
ON CONFLICT(id) DO UPDATE SET
  favorite_count = excluded.favorite_count,
  views_count = excluded.views_count,
  retweet_count = excluded.retweet_count,
  bookmark_count = excluded.bookmark_count,
  quote_count = excluded.quote_count,
  reply_count = excluded.reply_count,
  updated_at = datetime('now');
-- Never touch primary_tag, confidence, classification_error
```

### Layer 2: Classification dedup (`ti classify`)
```sql
-- Only classify unclassified tweets
SELECT * FROM tweets WHERE primary_tag IS NULL AND classification_error IS NULL;
-- Retry failed: ti classify --retry-failed
SELECT * FROM tweets WHERE primary_tag IS NULL AND classification_error IS NOT NULL;
```

### Layer 3: Watermark tracking
- `metadata.latest_tweet_id` / `latest_tweet_date` for display only
- Never used to filter imports — always deduplicate by tweet ID
- `import_log` tracks every sync operation

## Classification Pipeline

### Prompt design
Haiku receives:
1. The full tag taxonomy with descriptions
2. A Chinese tech slang glossary (cc=Claude Code, etc.)
3. A batch of 10-20 tweets (id + full_text + screen_name)
4. Instruction: return JSON array with `{id, primary_tag, tags[], confidence, summary, lang}`

### Execution via codebridge
```bash
codebridge submit \
  --engine claude-code \
  --model haiku \
  --workspace /Volumes/DevWork/homebrew/twitter-insights \
  --message "<classification prompt with tweets>" \
  --wait
```

### Error handling
- API failure → store tweet with `classification_error`, don't block import
- `ti classify --retry-failed` re-processes failed tweets
- `confidence < 0.6` → flagged for human review

## CLI Output

### Global flags
- `--format human|json|brief` (default: human)
- `--limit N` (default: 20 human, 50 json)
- `--offset N` (default: 0)

### JSON envelope (consistent across all commands)
```json
{
  "command": "search",
  "query": "MCP server",
  "total": 84,
  "returned": 20,
  "offset": 0,
  "results": [
    {
      "id": "...",
      "author": "@screen_name",
      "author_name": "Display Name",
      "created_at": "2026-02-21",
      "text": "...",
      "summary": "...",
      "url": "https://twitter.com/...",
      "tags": ["mcp", "claude-code-tools"],
      "primary_tag": "mcp",
      "confidence": 0.92,
      "engagement": {
        "likes": 18,
        "bookmarks": 41,
        "views": 32748
      }
    }
  ]
}
```

### Search ranking
```sql
-- Two-factor: text relevance (70%) + engagement signal (30%)
ORDER BY (bm25(tweets_fts) * -0.7 + log(1 + bookmark_count + favorite_count * 0.5) * 0.3) DESC
```

`--sort recent|relevant|popular` to override default.

## Tech Stack

- Python 3 + Typer + Rich
- SQLite3 (built-in) + FTS5 trigram
- codebridge for Haiku classification dispatch

## Current Data Snapshot

- **File:** `twitter-tweets-1771658347735.json`
- **Tweets:** 340
- **Date range:** 2025-08-28 to 2026-02-21
- **Latest tweet ID:** `2025033171864354981` (@shao__meng, 2026-02-21 10:21:46)
- **Authors:** 202 unique
- **Language:** ~80% Chinese, ~20% English
- **Top authors:** @dotey (18), @vista8 (11), @yetone (11)
