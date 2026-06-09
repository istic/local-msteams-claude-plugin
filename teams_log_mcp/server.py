"""MCP server exposing Teams conversation data."""

from __future__ import annotations

import os
import pathlib
import platform
import re

from mcp.server.fastmcp import FastMCP

from .cache import TeamsCache

mcp = FastMCP("teams-log", instructions="Access Microsoft Teams conversation history")
_cache: TeamsCache | None = None

_TYPE_ORDER = ["Space", "Topic", "Chat", "Meeting", "Thread"]


def _default_teams_root() -> str:
    """Return the default Teams WV2Profile_tfw path for the current OS.

    Tries the known package path first; falls back to globbing for WV2Profile_tfw
    in case the package name/identifier has changed.
    """
    system = platform.system()

    if system == "Darwin":
        home = pathlib.Path.home()
        candidate = (
            home
            / "Library/Containers/com.microsoft.teams2/Data/Library"
            / "Application Support/Microsoft/MSTeams/EBWebView/WV2Profile_tfw"
        )
        if candidate.exists():
            return str(candidate)
        matches = sorted(
            (home / "Library/Containers").glob(
                "*/Data/Library/Application Support/Microsoft/MSTeams/EBWebView/WV2Profile_tfw"
            )
        )
        return str(matches[0]) if matches else ""

    if system == "Windows":
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        if not local_app_data:
            return ""
        base = pathlib.Path(local_app_data)
        candidate = (
            base
            / "Packages/MSTeams_8wekyb3d8bbwe/LocalCache"
            / "Microsoft/MSTeams/EBWebView/WV2Profile_tfw"
        )
        if candidate.exists():
            return str(candidate)
        matches = sorted(
            (base / "Packages").glob(
                "MSTeams_*/LocalCache/Microsoft/MSTeams/EBWebView/WV2Profile_tfw"
            )
        )
        return str(matches[0]) if matches else ""

    return ""


def _get_cache() -> TeamsCache | None:
    global _cache
    if _cache is None:
        teams_root = _default_teams_root()
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


def _strip_html(html: str | bytes) -> str:
    if not html:
        return ""
    if isinstance(html, bytes):
        html = html.decode("utf-8", errors="replace")
    return re.sub(r"<[^>]+>", "", html).strip()


def _strip_content(messages: list[dict]) -> list[dict]:
    return [{**m, "content": _strip_html(m.get("content") or "")} for m in messages]


# --- list_conversations ---


def _list_conversations(cache: TeamsCache) -> dict:
    data = cache.get()
    if "error" in data:
        return {"error": f"Failed to load Teams data: {data['error']}"}
    result = []
    for conv_id, conv in data["conversations"].items():
        msgs = data["messages_by_conv"].get(conv_id, [])
        if not msgs:
            continue
        timestamps = [m["timestamp"] for m in msgs if m.get("timestamp")]
        result.append(
            {
                "id": conv_id,
                "type": conv["type"],
                "displayName": data["display_names"].get(conv_id, conv_id),
                "messageCount": len(msgs),
                "dateRange": {
                    "first": min(timestamps) if timestamps else None,
                    "last": max(timestamps) if timestamps else None,
                },
            }
        )
    result.sort(
        key=lambda c: (
            _TYPE_ORDER.index(c["type"]) if c["type"] in _TYPE_ORDER else 99,
            c["displayName"].lower(),
        )
    )
    return {"conversations": result}


@mcp.tool()
def list_conversations() -> dict:
    """List all Teams chats, channels, and meetings with message counts and date ranges."""
    cache = _get_cache()
    if cache is None:
        return {"error": "TEAMS_ROOT not set. Check your extension configuration."}
    return _list_conversations(cache)


# --- get_messages ---


def _get_messages(
    cache: TeamsCache,
    conversation: str,
    limit: int = 100,
    before: str | None = None,
    after: str | None = None,
) -> dict:
    data = cache.get()
    if "error" in data:
        return {"error": f"Failed to load Teams data: {data['error']}"}
    conv_id = _find_conversation_id(data, conversation)
    if conv_id is None:
        return {"error": f"Conversation not found: {conversation!r}"}

    msgs = list(data["messages_by_conv"].get(conv_id, []))
    if after:
        msgs = [m for m in msgs if m.get("timestamp") and m["timestamp"] > after]
    if before:
        msgs = [m for m in msgs if m.get("timestamp") and m["timestamp"] < before]
    msgs = msgs[: min(limit, 500)]

    display = data["display_names"].get(conv_id, conv_id)
    note = f"Matched '{display}' for query {conversation!r}" if conv_id != conversation else None

    return {
        "conversationId": conv_id,
        "displayName": display,
        "note": note,
        "messageCount": len(msgs),
        "messages": _strip_content(msgs),
    }


@mcp.tool()
def get_messages(
    conversation: str,
    limit: int = 100,
    before: str | None = None,
    after: str | None = None,
) -> dict:
    """Get messages from a Teams conversation by name or ID.

    Args:
        conversation: Conversation ID (exact) or display name (case-insensitive substring).
        limit: Maximum messages to return (default 100, max 500).
        before: Return only messages before this ISO 8601 timestamp.
        after: Return only messages after this ISO 8601 timestamp.
    """
    cache = _get_cache()
    if cache is None:
        return {"error": "TEAMS_ROOT not set. Check your extension configuration."}
    return _get_messages(cache, conversation, limit=limit, before=before, after=after)


# --- search_messages ---


def _search_messages(
    cache: TeamsCache,
    query: str,
    conversation: str | None = None,
    limit: int = 50,
) -> dict:
    data = cache.get()
    if "error" in data:
        return {"error": f"Failed to load Teams data: {data['error']}"}
    query_lower = query.lower()

    if conversation:
        conv_id = _find_conversation_id(data, conversation)
        if conv_id is None:
            return {"error": f"Conversation not found: {conversation!r}"}
        search_ids = [conv_id]
    else:
        search_ids = list(data["messages_by_conv"].keys())

    results = []
    for cid in search_ids:
        display = data["display_names"].get(cid, cid)
        conv_type = data["conversations"].get(cid, {}).get("type", "Unknown")
        for msg in data["messages_by_conv"].get(cid, []):
            if query_lower in _strip_html(msg.get("content") or "").lower():
                results.append(
                    {
                        **msg,
                        "content": _strip_html(msg.get("content") or ""),
                        "conversationDisplayName": display,
                        "conversationType": conv_type,
                    }
                )

    return {
        "query": query,
        "totalCount": len(results),
        "resultCount": len(results[:limit]),
        "results": results[:limit],
    }


@mcp.tool()
def search_messages(
    query: str,
    conversation: str | None = None,
    limit: int = 50,
) -> dict:
    """Search for messages containing a string across Teams conversations.

    Args:
        query: Case-insensitive text to search for.
        conversation: Optional conversation name or ID to restrict the search.
        limit: Maximum results to return (default 50).
    """
    cache = _get_cache()
    if cache is None:
        return {"error": "TEAMS_ROOT not set. Check your extension configuration."}
    return _search_messages(cache, query, conversation=conversation, limit=limit)


# --- get_conversation_summary ---


def _get_conversation_summary(cache: TeamsCache, conversation: str) -> dict:
    data = cache.get()
    if "error" in data:
        return {"error": f"Failed to load Teams data: {data['error']}"}
    conv_id = _find_conversation_id(data, conversation)
    if conv_id is None:
        return {"error": f"Conversation not found: {conversation!r}"}

    conv = data["conversations"].get(conv_id, {})
    msgs = data["messages_by_conv"].get(conv_id, [])
    display = data["display_names"].get(conv_id, conv_id)
    timestamps = [m["timestamp"] for m in msgs if m.get("timestamp")]

    participants: list[str] = []
    seen: set[str] = set()
    for m in msgs:
        s = m.get("sender") or ""
        if s and s not in seen:
            participants.append(s)
            seen.add(s)

    note = f"Matched '{display}' for query {conversation!r}" if conv_id != conversation else None

    return {
        "conversationId": conv_id,
        "displayName": display,
        "type": conv.get("type", "Unknown"),
        "note": note,
        "messageCount": len(msgs),
        "participants": participants,
        "dateRange": {
            "first": min(timestamps) if timestamps else None,
            "last": max(timestamps) if timestamps else None,
        },
        "recentMessages": _strip_content(msgs[-5:]),
    }


@mcp.tool()
def get_conversation_summary(conversation: str) -> dict:
    """Get a summary of a Teams conversation.

    Returns participants, message count, date range, and the 5 most recent messages.

    Args:
        conversation: Conversation ID (exact) or display name (case-insensitive substring).
    """
    cache = _get_cache()
    if cache is None:
        return {"error": "TEAMS_ROOT not set. Check your extension configuration."}
    return _get_conversation_summary(cache, conversation)
