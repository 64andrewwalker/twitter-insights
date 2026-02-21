"""Tag taxonomy: 7 categories, 32 tags."""

TAXONOMY: dict[str, dict[str, str]] = {
    "claude-code": {
        "claude-code-workflow": "Usage patterns, session management, context strategies, CLAUDE.md",
        "claude-code-skills": "Skills/SKILL.md, skill repos, Context7, Vercel skills",
        "claude-code-hooks": "Hooks, plugins, pre/post hooks",
        "claude-code-memory": "Memory persistence, context carryover",
        "claude-code-tools": "Third-party tools, wrappers, IDEs integrating CC",
    },
    "agent-engineering": {
        "multi-agent-orchestration": "Multi-agent setups, sub-agents, orchestrator patterns",
        "agent-memory": "Agent memory architecture, persistent memory systems",
        "agent-autonomy": "Autonomous agents, always-on assistants",
        "agent-browser": "Browser automation for agents",
        "agent-sdk": "Agent SDKs, programmatic agent construction",
    },
    "llm-models": {
        "model-comparison": "Side-by-side rankings, benchmarks",
        "model-release": "New model announcements",
        "api-access": "API pricing, proxies, subscription strategies",
        "local-models": "Local inference, GPU selection, VRAM",
        "reasoning-models": "Chain-of-thought, o1/o3, thinking models",
    },
    "vibe-coding": {
        "vibe-coding-workflow": "AI-assisted dev process",
        "vibe-coding-ui": "AI-generated frontend, design tools",
        "vibe-coding-philosophy": "Opinions on AI coding quality, future of SE",
    },
    "tools-and-ecosystem": {
        "mcp": "Model Context Protocol servers, setup",
        "prompt-engineering": "System prompt design, CLAUDE.md optimization",
        "open-source": "Open-source project highlights",
        "devtools": "Non-AI dev tooling (tmux, monorepo, GitHub Actions)",
        "ai-product-design": "AI-native product design philosophy",
    },
    "specific-products": {
        "cursor": "Cursor IDE",
        "openclaw": "OpenClaw/Clawdbot/MoltBot/NanoClaw",
        "opencode": "Opencode, Oh My OpenCode",
        "gemini-ecosystem": "Gemini CLI, Google AI, Chrome integration",
        "codex": "OpenAI Codex CLI, AGENTS.md",
        "kimi": "Kimi/Moonshot AI models",
    },
    "meta-and-noise": {
        "ai-industry": "Industry news, layoffs, enterprise AI",
        "learning-resources": "Reading lists, paper summaries, podcast recs",
        "offbeat": "Personal life, health tips, off-topic",
    },
}

ALL_TAGS: dict[str, str] = {}
for category, tags in TAXONOMY.items():
    for tag_name, description in tags.items():
        ALL_TAGS[tag_name] = category


def get_category(tag_name: str) -> str | None:
    return ALL_TAGS.get(tag_name)
