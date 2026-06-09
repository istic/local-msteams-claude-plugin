---
name: Teams Conversations
description: Use when the user asks about past decisions, meeting outcomes, team discussions, messages from colleagues, or anything that might have been discussed in Microsoft Teams. Also use when the user asks to search Teams, find a conversation, or recall what was said about a topic.
---

# Teams Conversations

This plugin provides read access to the user's Microsoft Teams conversation history via four MCP tools. Data is loaded directly from the local Teams IndexedDB cache — no network call required, and Teams can be running or closed.

## Available Tools

**`list_conversations`** — list all chats, channels, and meetings with message counts and date ranges. Call this first when you need to orient yourself or when the user asks "what channels do I have" or similar.

**`get_messages(conversation, limit?, before?, after?)`** — fetch messages from a specific conversation. `conversation` accepts an exact ID or a case-insensitive display name substring (e.g. `"engineering"` matches `"Engineering - General"`). Use `before`/`after` (ISO 8601) to narrow by date.

**`search_messages(query, conversation?, limit?)`** — full-text search across all conversations. Use this when the user asks about a topic without specifying a channel.

**`get_conversation_summary(conversation)`** — get participants, date range, message count, and the 5 most recent messages. Use this before `get_messages` when you need a quick orientation or the user just wants context rather than a full history.

## When to Use

- User asks "what did we decide about X?" → `search_messages("X")`
- User asks "what was discussed in the engineering channel?" → `get_messages("engineering")`
- User asks "who was in the meeting about Y?" → `search_messages("Y")` then `get_conversation_summary`
- User asks "find that message about Z" → `search_messages("Z")`
- User asks "what channels do I have?" → `list_conversations()`

## Data Freshness

The tool caches Teams data in memory for 5 minutes. If the user says the data looks stale, note that they may need to restart the MCP server or wait for the cache to refresh.
