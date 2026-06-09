# local-msteams-claude-plugin

Exposes your Microsoft Teams conversation history to Claude via four MCP tools. Works as a **Claude Code plugin** and a **Claude Desktop extension**.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Microsoft Teams desktop app (new Teams, WebView2-based)

No manual path configuration needed — the Teams data directory is detected automatically from the OS.

## Install: Claude Code plugin

Add to `~/.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "teams-log": {
      "source": {
        "source": "github",
        "repo": "istic/local-msteams-claude-plugin"
      }
    }
  },
  "enabledPlugins": {
    "teams-log@teams-log": true
  }
}
```

Then run `/reload-plugins` in Claude Code.

## Install: Claude Desktop extension

Download `teams-log.mcpb` from the [latest release](https://github.com/istic/local-msteams-claude-plugin/releases/latest) and open it with Claude Desktop.

## Available Tools

| Tool | Description |
|------|-------------|
| `list_conversations` | List all chats, channels, and meetings |
| `get_messages` | Fetch messages from a conversation by name or ID |
| `search_messages` | Full-text search across all conversations |
| `get_conversation_summary` | Participants, date range, and 5 most recent messages |

## Data freshness

Data is read directly from the Teams IndexedDB cache — no need to close Teams. Results are cached in memory for 5 minutes.

## Development

```bash
uv sync
uv run pytest tests/ --ignore=tests/test_integration.py
```

Integration test (requires Teams installed):
```bash
uv run pytest tests/test_integration.py -v -s
```

Build release artifacts:
```bash
uv run build-dxt
# outputs build/teams-log.zip (Claude Code) and build/teams-log.mcpb (Claude Desktop)
```

Releases are created automatically by GitHub Actions when a tag is pushed:
```bash
git tag v0.1.0 && git push origin v0.1.0
```
