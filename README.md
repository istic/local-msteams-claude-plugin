# Teams Log MCP Desktop Extension

Exposes your Microsoft Teams conversation history to Claude Desktop via four MCP tools.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Microsoft Teams desktop app (new Teams, WebView2-based)

## Installing the DXT

1. Download or build `teams-log.dxt` (see below).
2. Open Claude Desktop → Settings → Extensions → Install from file.
3. Select `teams-log.dxt`.
4. When prompted, enter your Teams data path:
   - **Windows:** `C:\Users\<you>\AppData\Local\Packages\MSTeams_8wekyb3d8bbwe\LocalCache\Microsoft\MSTeams\EBWebView\WV2Profile_tfw`
   - **macOS:** `~/Library/Containers/com.microsoft.teams2/Data/Library/Application Support/Microsoft/MSTeams/EBWebView/WV2Profile_tfw`

## Building the DXT

```bash
poetry install
poetry run build-dxt
```

This produces `teams-log.dxt` in the project root.

## Available Tools

| Tool | Description |
|------|-------------|
| `list_conversations` | List all chats, channels, and meetings |
| `get_messages` | Fetch messages from a conversation by name or ID |
| `search_messages` | Full-text search across all conversations |
| `get_conversation_summary` | Participants, date range, and 5 most recent messages |

## Data freshness

The extension caches Teams data in memory for 5 minutes. Data is read directly from the Teams IndexedDB — no need to close Teams first.

## Development

```bash
poetry install
poetry run pytest tests/ --ignore=tests/test_integration.py
```

For the integration test (requires Teams data):
```bash
TEAMS_ROOT=/path/to/WV2Profile_tfw poetry run pytest tests/test_integration.py -v -s
```
