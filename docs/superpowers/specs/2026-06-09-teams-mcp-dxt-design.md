# Teams MCP Desktop Extension — Design Spec

**Date:** 2026-06-09
**Status:** Approved

## Overview

Add a `teams_log_mcp/` module to this repo that exposes Teams conversation data as an MCP server, packaged as a shareable `.dxt` file for Claude Desktop. Users install the extension, set their `TEAMS_ROOT` path, and Claude Desktop can then search, list, and retrieve Teams messages directly from the local IndexedDB cache.

## Architecture

### New module structure

```
teams_log_mcp/
  __init__.py
  __main__.py      # entry point: python -m teams_log_mcp
  server.py        # FastMCP server + tool definitions
  cache.py         # TTL-based cache wrapping TeamsExporter

manifest.json      # DXT manifest — tools description, user config fields
build_dxt.py       # script: produces teams-log.dxt
```

Sits alongside the existing `teams_log_export/` module. Imports `TeamsExporter` directly.

### Runtime

The MCP server runs as a stdio subprocess managed by Claude Desktop. The manifest uses `uv` as the runner so Python dependencies resolve automatically — no manual `pip install` for end users. The only prerequisite is Python + uv installed.

### DXT packaging

`build_dxt.py` zips the following into `teams-log.dxt`:
- `manifest.json`
- `teams_log_mcp/`
- `teams_log_export/`
- `pylib/ccl_chromium_reader/`
- `pyproject.toml`

A `build-dxt` Poetry script entry makes this runnable as `poetry run build-dxt`.

### User configuration

`TEAMS_ROOT` is declared as a required string field in `manifest.json`. Claude Desktop prompts for it on install. Platform paths:

- **Windows:** `%LOCALAPPDATA%\Packages\MSTeams_8wekyb3d8bbwe\LocalCache\Microsoft\MSTeams\EBWebView\WV2Profile_tfw`
- **macOS:** `~/Library/Containers/com.microsoft.teams2/Data/Library/Application Support/Microsoft/MSTeams/EBWebView/WV2Profile_tfw`

### Cache

`cache.py` provides a `TeamsCache` class wrapping `TeamsExporter`. On each tool call, if the cache is uninitialised or older than 5 minutes (`_loaded_at` timestamp), it calls `load_channel_names()`, `load_conversations()`, `load_messages()`, and `build_user_map()` before serving the result. The IndexedDB is opened read-only and is safe to read alongside a running Teams instance.

## MCP Tools

### `list_conversations()`

No required parameters. Returns all conversations as `{id, type, displayName, messageCount, dateRange}`, grouped by type (channels, chats, meetings, other). Used by Claude to discover what data is available.

### `get_messages(conversation, limit?, before?, after?)`

- `conversation`: conversation ID (exact) or display name (case-insensitive substring match; first match wins)
- `limit`: default 100, max 500
- `before` / `after`: ISO 8601 timestamps for time-bounded fetches

Returns messages with sender, timestamp, and plain-text content (HTML stripped).

### `search_messages(query, conversation?, limit?)`

Case-insensitive substring search across all message content. Optional `conversation` narrows scope. `limit` defaults to 50. Returns messages with their conversation context (name, type) included.

### `get_conversation_summary(conversation)`

Returns: display name, type, participant names, message count, first/last message timestamps, and the 5 most recent messages as a preview. Avoids needing a full `get_messages` call just to characterise a conversation.

## Error Handling

- Missing or invalid `TEAMS_ROOT`: every tool returns `"Teams data not found at <path>. Check your TEAMS_ROOT setting."` rather than raising.
- IndexedDB read failure: cache returns whatever partial data loaded; partial results are better than nothing.
- Fuzzy name match: tool notes the matched name in the response, e.g. `"Matched 'General — Engineering' for query 'engineering general'"`.

## Testing

- Unit tests for `cache.py` using pre-exported JSON fixtures — no IndexedDB required. Covers TTL logic, fuzzy name matching, search, and time-bounded fetches.
- One integration smoke test gated on `TEAMS_ROOT` being set in the environment; skipped otherwise.
- Manual DXT install steps documented in `README.md`.

## Out of scope

- Writing or sending messages
- Real-time / push updates
- Attachments or media content
- Authentication / OAuth (reads local cache only)
