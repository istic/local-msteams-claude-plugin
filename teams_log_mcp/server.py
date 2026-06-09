"""MCP server exposing Teams conversation data."""

from __future__ import annotations

import os
import re

from mcp.server.fastmcp import FastMCP

from .cache import TeamsCache

mcp = FastMCP("teams-log", instructions="Access Microsoft Teams conversation history")
_cache: TeamsCache | None = None

_TYPE_ORDER = ["Space", "Topic", "Chat", "Meeting", "Thread"]


def _get_cache() -> TeamsCache | None:
    global _cache
    if _cache is None:
        teams_root = os.environ.get("TEAMS_ROOT", "").strip()
        if not teams_root:
            return None
        _cache = TeamsCache(teams_root)
    return _cache


def _find_conversation_id(data: dict, conversation: str) -> str | None:
    """Return conversation ID by exact ID or case-insensitive display name substring."""
    if conversation in data["conversations"]:
        return conversation
    conv_lower = conversation.lower()
    for conv_id, display in data["display_names"].items():
        if conv_lower in display.lower():
            return conv_id
    return None


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html).strip() if html else ""


def _strip_content(messages: list[dict]) -> list[dict]:
    return [{**m, "content": _strip_html(m.get("content") or "")} for m in messages]


# --- list_conversations ---

def _list_conversations(cache: TeamsCache) -> dict:
    data = cache.get()
    result = []
    for conv_id, conv in data["conversations"].items():
        msgs = data["messages_by_conv"].get(conv_id, [])
        if not msgs:
            continue
        timestamps = [m["timestamp"] for m in msgs if m.get("timestamp")]
        result.append({
            "id": conv_id,
            "type": conv["type"],
            "displayName": data["display_names"].get(conv_id, conv_id),
            "messageCount": len(msgs),
            "dateRange": {
                "first": min(timestamps) if timestamps else None,
                "last": max(timestamps) if timestamps else None,
            },
        })
    result.sort(key=lambda c: (
        _TYPE_ORDER.index(c["type"]) if c["type"] in _TYPE_ORDER else 99,
        c["displayName"].lower(),
    ))
    return {"conversations": result}


@mcp.tool()
def list_conversations() -> dict:
    """List all Teams chats, channels, and meetings with message counts and date ranges."""
    cache = _get_cache()
    if cache is None:
        return {"error": "TEAMS_ROOT not set. Check your extension configuration."}
    return _list_conversations(cache)
