"""Generate a sample digest HTML for visual verification."""

import json
import sys

sys.path.insert(0, "src")

from pathlib import Path

from ti.digest import render_digest_html

SAMPLE_DATA = {
    "period": "2026-W08",
    "period_label": "2026-W08 (2\u670816\u65e5 - 2\u670822\u65e5)",
    "generated_at": "2026-02-21T21:30:00",
    "stats": {
        "total_tweets": 42,
        "total_authors": 28,
        "date_range": ["2026-02-16", "2026-02-22"],
    },
    "tldr": "\u672c\u5468\u6700\u5927\u7684\u65b0\u95fb\u662f Claude Code 4.5 \u53d1\u5e03\u540e\u793e\u533a\u7684\u75af\u72c2\u5b9e\u9a8c\u2014\u2014\u4ece CLAUDE.md \u6700\u4f73\u5b9e\u8df5\u5230\u591a agent \u534f\u4f5c\u6d41\u6c34\u7ebf\uff0cCC \u751f\u6001\u6b63\u5728\u4ee5\u8089\u773c\u53ef\u89c1\u7684\u901f\u5ea6\u6210\u719f\u3002\u4e0e\u6b64\u540c\u65f6\uff0cMCP \u6084\u6084\u6210\u4e3a\u4e86\u4e8b\u5b9e\u4e0a\u7684 agent-tool \u534f\u8bae\u6807\u51c6\u3002",
    "hot_take": "\u770b\u5b8c\u8fd9\u5468 42 \u6761\u63a8\u6587\uff0c\u4e00\u4e2a\u5f3a\u70c8\u7684\u611f\u89c9\uff1a\u6211\u4eec\u6b63\u5728\u89c1\u8bc1 '\u5f00\u53d1\u8005\u5de5\u5177' \u548c 'AI agent' \u8fd9\u4e24\u4e2a\u54c1\u7c7b\u7684\u5408\u5e76\u3002CC \u4e0d\u518d\u662f IDE \u7684\u9644\u5c5e\u54c1\uff0c\u5b83\u6b63\u5728\u53d8\u6210\u5f00\u53d1\u8005\u7684 operating system\u3002\u4e09\u4e2a\u6708\u540e\u56de\u770b\u8fd9\u5468\uff0c\u53ef\u80fd\u662f\u4e2a\u8f6c\u6298\u70b9\u3002",
    "topics": [
        {
            "category": "claude-code",
            "category_label": "Claude Code",
            "headline": "CC \u793e\u533a\u5728\u75af\u72c2\u8bd5\u9a8c CLAUDE.md \u7684\u6781\u9650",
            "commentary": "\u8fd9\u5468 CC \u751f\u6001\u7206\u53d1\u4e86\u3002@dotey \u5206\u4eab\u4e86\u4ed6\u7684 10 \u4e07\u5b57 CLAUDE.md\uff0c\u793e\u533a\u70b8\u4e86\u2014\u2014\u6709\u4eba\u8bf4\u8fd9\u662f prompt engineering \u7684\u7ec8\u6781\u5f62\u6001\uff0c\u6709\u4eba\u8bf4\u8fd9\u662f\u5728\u7528\u81ea\u7136\u8bed\u8a00\u5199\u4ee3\u7801\u3002@karpathy \u5219\u4ece\u53e6\u4e00\u4e2a\u89d2\u5ea6\u5207\u5165\uff0c\u8ba8\u8bba\u4e86 CC \u5728\u5927\u578b monorepo \u4e2d\u7684\u5de5\u4f5c\u6d41\u3002\u6709\u610f\u601d\u7684\u662f\u4e24\u4eba\u5f97\u51fa\u4e86\u5b8c\u5168\u76f8\u53cd\u7684\u7ed3\u8bba\uff1adotey \u8ba4\u4e3a CLAUDE.md \u8d8a\u8be6\u7ec6\u8d8a\u597d\uff0ckarpathy \u89c9\u5f97\u5e94\u8be5\u4fdd\u6301\u7cbe\u7b80\u8ba9 AI \u81ea\u5df1\u63a2\u7d22\u3002",
            "vibe": "hot",
            "tweets": [
                {
                    "id": "t001",
                    "author": "@dotey",
                    "author_name": "\u5b9d\u7389",
                    "text": "\u5206\u4eab\u4e00\u4e0b\u6211\u7684 CLAUDE.md \u6700\u4f73\u5b9e\u8df5\u3002\u7ecf\u8fc7\u4e09\u4e2a\u6708\u7684\u8fed\u4ee3\uff0c\u6211\u53d1\u73b0\u6700\u91cd\u8981\u7684\u662f\u628a\u4f60\u7684\u5de5\u4f5c\u6d41\u7a0b\u5199\u6e05\u695a\uff0c\u800c\u4e0d\u662f\u5199\u4e00\u5806\u89c4\u5219...",
                    "summary": "Detailed CLAUDE.md best practices after 3 months of iteration",
                    "primary_tag": "claude-code-workflow",
                    "url": "https://x.com/dotey/status/t001",
                    "created_at": "2026-02-18",
                    "must_read": True,
                    "engagement": {"likes": 342, "bookmarks": 188, "views": 52000},
                },
                {
                    "id": "t002",
                    "author": "@karpathy",
                    "author_name": "Andrej Karpathy",
                    "text": "I've been using Claude Code on a large monorepo and here's what I learned: keep your CLAUDE.md minimal...",
                    "summary": "Minimal CLAUDE.md approach works better for large monorepos",
                    "primary_tag": "claude-code-workflow",
                    "url": "https://x.com/karpathy/status/t002",
                    "created_at": "2026-02-19",
                    "must_read": True,
                    "engagement": {"likes": 1205, "bookmarks": 567, "views": 180000},
                },
                {
                    "id": "t003",
                    "author": "@swyx",
                    "author_name": "swyx",
                    "text": "CC skills are basically composable prompt modules. This changes everything about how we think about developer tooling...",
                    "summary": "CC skills as composable prompt modules represent a paradigm shift",
                    "primary_tag": "claude-code-skills",
                    "url": "https://x.com/swyx/status/t003",
                    "created_at": "2026-02-20",
                    "must_read": False,
                    "engagement": {"likes": 89, "bookmarks": 45, "views": 12000},
                },
            ],
        },
        {
            "category": "agent-engineering",
            "category_label": "Agent Engineering",
            "headline": "\u591a Agent \u7f16\u6392\u4ece\u73a9\u5177\u8d70\u5411\u751f\u4ea7",
            "commentary": "\u672c\u5468 agent \u9886\u57df\u6700\u503c\u5f97\u5173\u6ce8\u7684\u662f\u4ece demo \u5230 production \u7684\u8fc7\u6e21\u3002\u51e0\u4e2a\u5b9e\u9645\u7684\u591a agent \u90e8\u7f72\u6848\u4f8b\u51fa\u73b0\u4e86\uff0c\u4e0d\u518d\u662f toy example\u3002@AndrewNg \u5206\u4eab\u7684 agent \u8bbe\u8ba1\u6a21\u5f0f\u603b\u7ed3\u7279\u522b\u503c\u5f97\u8bfb\u2014\u2014\u4ed6\u628a\u73b0\u6709\u7684\u6a21\u5f0f\u5f52\u7eb3\u6210\u4e86\u56db\u7c7b\u3002",
            "vibe": "steady",
            "tweets": [
                {
                    "id": "t004",
                    "author": "@AndrewNg",
                    "author_name": "Andrew Ng",
                    "text": "Four design patterns for AI agents that actually work in production...",
                    "summary": "Four production-ready AI agent design patterns",
                    "primary_tag": "multi-agent-orchestration",
                    "url": "https://x.com/AndrewNg/status/t004",
                    "created_at": "2026-02-17",
                    "must_read": True,
                    "engagement": {"likes": 2100, "bookmarks": 890, "views": 350000},
                },
                {
                    "id": "t005",
                    "author": "@langaborkedev",
                    "author_name": "LangChain Dev",
                    "text": "\u6211\u4eec\u5728\u751f\u4ea7\u73af\u5883\u4e2d\u90e8\u7f72\u4e86\u4e00\u4e2a 5-agent \u7684\u534f\u4f5c\u7cfb\u7edf\uff0c\u5904\u7406\u5ba2\u670d\u5de5\u5355\u3002\u5206\u4eab\u4e00\u4e0b\u8e29\u8fc7\u7684\u5751...",
                    "summary": "Production deployment lessons from a 5-agent customer service system",
                    "primary_tag": "multi-agent-orchestration",
                    "url": "https://x.com/langaborkedev/status/t005",
                    "created_at": "2026-02-19",
                    "must_read": False,
                    "engagement": {"likes": 156, "bookmarks": 78, "views": 25000},
                },
            ],
        },
        {
            "category": "tools-and-ecosystem",
            "category_label": "Tools & Ecosystem",
            "headline": "MCP \u6084\u6084\u53d8\u6210\u4e86\u4e8b\u5b9e\u6807\u51c6",
            "commentary": "\u6ca1\u6709\u5927\u65b0\u95fb\uff0c\u4f46\u770b\u8d8b\u52bf\u5f88\u660e\u663e\uff1a\u8d8a\u6765\u8d8a\u591a\u7684\u5de5\u5177\u5f00\u59cb\u539f\u751f\u652f\u6301 MCP\u3002\u672c\u5468\u53c8\u6709\u4e09\u4e2a\u4e3b\u6d41 IDE \u5ba3\u5e03\u96c6\u6210\u3002\u91cf\u53d8\u5feb\u5230\u8d28\u53d8\u4e86\u3002",
            "vibe": "steady",
            "tweets": [
                {
                    "id": "t006",
                    "author": "@alexalbert__",
                    "author_name": "Alex Albert",
                    "text": "MCP adoption is accelerating. This week: VS Code, IntelliJ, and Neovim all shipped MCP support...",
                    "summary": "Three major IDEs shipped MCP support in the same week",
                    "primary_tag": "mcp",
                    "url": "https://x.com/alexalbert__/status/t006",
                    "created_at": "2026-02-20",
                    "must_read": False,
                    "engagement": {"likes": 445, "bookmarks": 210, "views": 78000},
                },
            ],
        },
        {
            "category": "meta-and-noise",
            "category_label": "Meta & Noise",
            "headline": "\u672c\u5468\u95f2\u804a\u533a",
            "commentary": "\u51e0\u6761\u884c\u4e1a\u516b\u5366\u548c\u751f\u6d3b\u63a8\u6587\uff0c\u6ca1\u4ec0\u4e48\u7279\u522b\u503c\u5f97\u6df1\u5165\u7684\u3002",
            "vibe": "quiet",
            "tweets": [
                {
                    "id": "t007",
                    "author": "@random_dev",
                    "author_name": "Random Dev",
                    "text": "\u4eca\u5929\u6478\u9c7c\u770b\u5230\u4e00\u4e2a\u6709\u8da3\u7684 GitHub repo...",
                    "summary": "Random interesting GitHub discovery",
                    "primary_tag": "offbeat",
                    "url": "https://x.com/random_dev/status/t007",
                    "created_at": "2026-02-21",
                    "must_read": False,
                    "engagement": {"likes": 12, "bookmarks": 3, "views": 800},
                },
            ],
        },
    ],
}


if __name__ == "__main__":
    out = Path("/tmp/ti-digest-sample.html")
    render_digest_html(SAMPLE_DATA, out)
    print(f"Sample digest written to {out}")
