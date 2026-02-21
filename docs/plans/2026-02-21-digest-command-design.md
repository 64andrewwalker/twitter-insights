# `ti digest` Command Design

**Date**: 2026-02-21
**Status**: Approved

## Problem

User collects 30-50 tweets/week but doesn't process them. Needs a batch digest that groups by topic, adds AI commentary, and renders as a visually appealing HTML page. Fits ADHD workflow: low-friction intake, batch processing.

## Solution: Local Grouping + AI Commentary + HTML Template

### Architecture (3 Layers)

```
CLI command → Python (query + group) → AI (commentary) → HTML template (render)
```

1. **Data layer** (`src/ti/digest.py`): Query DB by date range → auto-classify if needed → group by tag category → produce structured JSON
2. **AI layer** (via codebridge): Receive summary list → return TL;DR, per-topic headlines/commentary, must-reads, hot take
3. **Template layer** (`src/ti/templates/digest.html`): React + Tailwind CDN, reads `window.__DIGEST_DATA__`, renders cards

### CLI Interface

```bash
ti digest                          # default: current ISO week
ti digest --period weekly          # same
ti digest --period monthly         # current month

ti digest --format json            # JSON output (agent-friendly)
ti digest --no-open                # generate but don't open browser
ti digest --save                   # also save to digests/2026-W08.html
ti digest --engine kimi-code       # AI engine (default: kimi-code)
ti digest --dry-run                # show tweet count, don't call AI
```

Output: `/tmp/ti-digest-2026-W08.html`, auto-opens in browser via `open` (macOS).

### AI Prompt Design

System prompt tells AI:

> Your reader is a heavy ADHD, high-IQ developer. They bookmarked lots of tweets but have no time to read. Write a digest they can't stop reading.
>
> Rules:
>
> - TL;DR = newsletter hook — one sentence capturing the week's most notable trend
> - Topic commentary must have opinions — not "8 tweets about CC", but "CC community is debating X, core disagreement is..."
> - Be sharp, witty, draw connections — "Interesting that @A and @B reached opposite conclusions the same week"
> - If a tweet is must-read, say so explicitly
> - Write in Chinese, English terms OK
> - Don't be boring. If a topic is unremarkable, say "nothing interesting here, skip"

AI input: structured JSON with summaries grouped by category (not full tweet text — saves tokens).

AI output:

```json
{
  "tldr": "本周的大新闻是...",
  "topics": [
    {
      "category": "claude-code",
      "headline": "CC 社区在吵 CLAUDE.md 到底该写多长",
      "commentary": "有态度的分析...",
      "must_read": ["tweet_id_1"],
      "vibe": "hot"
    }
  ],
  "hot_take": "看完本周的收藏，我有个感觉：..."
}
```

Fields:

- `headline`: Catchy one-liner per topic (more engaging than category name)
- `must_read`: Tweet IDs the AI thinks deserve full reading
- `vibe`: `hot` / `steady` / `quiet` — template uses different colors/badges
- `hot_take`: Optional global spicy take at the end

### Data Structure (`window.__DIGEST_DATA__`)

```json
{
  "period": "2026-W08",
  "period_label": "2026年2月17日 - 2月23日",
  "generated_at": "2026-02-21T21:30:00",
  "stats": {
    "total_tweets": 42,
    "total_authors": 28,
    "date_range": ["2026-02-17", "2026-02-23"]
  },
  "tldr": "本周的大新闻是...",
  "hot_take": "看完本周的收藏...",
  "topics": [
    {
      "category": "claude-code",
      "category_label": "Claude Code",
      "headline": "CC 社区在吵...",
      "commentary": "...",
      "vibe": "hot",
      "tweets": [
        {
          "id": "123456",
          "author": "@dotey",
          "author_name": "宝玉",
          "text": "原文前 200 字...",
          "summary": "AI 生成的一句话摘要",
          "primary_tag": "claude-code-workflow",
          "url": "https://x.com/...",
          "created_at": "2026-02-19",
          "must_read": true,
          "engagement": { "likes": 42, "bookmarks": 15, "views": 3200 }
        }
      ]
    }
  ]
}
```

Tweets within each topic sorted by engagement (most popular first). Empty categories omitted.

### HTML Template

Single self-contained HTML file:

- React 18 via CDN (+ Babel standalone for JSX)
- Tailwind CSS via CDN
- Dark theme, shadcn-inspired components (Card, Badge, Separator)
- Card grid layout for tweets within each topic
- Tweet cards link to original tweet URL
- `must_read` tweets get a highlight badge
- `vibe` badges: 🔥 hot (red), 📈 steady (blue), 🌙 quiet (gray)
- Data injected via `<script>window.__DIGEST_DATA__ = {{DATA}}</script>`
- Python does: `template.replace("{{DATA}}", json.dumps(data))`

### Unclassified Tweet Handling

If the date range contains unclassified tweets, `ti digest` automatically runs classification (same as `ti classify`) before generating the digest. Progress shown in terminal.

### File Layout

```
src/ti/
  digest.py            # Data queries, AI call, HTML generation
  templates/
    digest.html        # React + Tailwind template
```

### Dependencies

No new Python dependencies. Template uses CDN-loaded JS/CSS (requires internet on first open, then cached by browser).
