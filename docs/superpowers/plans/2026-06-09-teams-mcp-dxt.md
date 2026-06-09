# Teams MCP Desktop Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `teams_log_mcp/` module and DXT packaging to expose Teams conversation data as four MCP tools in Claude Desktop.

**Architecture:** A FastMCP server (`teams_log_mcp/server.py`) wraps a `TeamsCache` class (`cache.py`) that lazily loads all data from `TeamsExporter` and caches it for 5 minutes. Each of the four tools delegates to a private function that accepts a `TeamsCache`, keeping tool logic testable without spinning up the MCP framework.

**Tech Stack:** Python 3.10+, `mcp>=1.0.0` (provides `FastMCP`), `uv` (DXT runtime), `pytest` (tests), existing `TeamsExporter` + `ccl_chromium_reader`.

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `pyproject.toml` | Modify | Add `mcp`, `ccl_chromium_reader` deps; add `teams_log_mcp` package; add scripts |
| `teams_log_export/exporter.py` | Modify | Add `compute_display_names()` public method |
| `teams_log_mcp/__init__.py` | Create | Empty package marker |
| `teams_log_mcp/cache.py` | Create | `TeamsCache` with 5-min TTL wrapping `TeamsExporter` |
| `teams_log_mcp/server.py` | Create | FastMCP server + 4 tool functions + private logic functions |
| `teams_log_mcp/__main__.py` | Create | `mcp.run()` entry point |
| `manifest.json` | Create | DXT manifest: server command, user config, tool listing |
| `build_dxt.py` | Create | Zip project files into `teams-log.dxt` |
| `tests/__init__.py` | Create | Empty |
| `tests/conftest.py` | Create | Shared fixture data dict |
| `tests/test_exporter_display_names.py` | Create | Unit tests for `compute_display_names()` |
| `tests/test_cache.py` | Create | Unit tests for TTL, reload, invalidate |
| `tests/test_server.py` | Create | Unit tests for all four tool logic functions |
| `tests/test_integration.py` | Create | Smoke test gated on `TEAMS_ROOT` env var |
| `README.md` | Create | DXT install instructions |

---

## Task 1: Update pyproject.toml

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add `mcp`, `ccl_chromium_reader`, and `pytest` dependencies; register packages and scripts**

Replace the entire `pyproject.toml` with:

```toml
[project]
name = "teams-log-export"
version = "0.1.0"
description = "Export Microsoft Teams chat and channel logs"
authors = [
    {name = "Nicholas Avenell"}
]
requires-python = ">=3.10"
dependencies = [
    "brotli (>=1.2.0,<2.0.0)",
    "python-dotenv (>=1.2.2,<2.0.0)",
    "mcp (>=1.0.0)",
    "ccl_chromium_reader @ file:pylib/ccl_chromium_reader",
]

[project.scripts]
teams-export = "teams_log_export.__main__:main"
teams-mcp = "teams_log_mcp.__main__:main"
build-dxt = "build_dxt:main"

[tool.poetry]
packages = [
    {include = "teams_log_export"},
    {include = "teams_log_mcp"},
]

[tool.poetry.group.dev.dependencies]
pytest = ">=7.0.0"

[build-system]
requires = ["poetry-core>=2.0.0,<3.0.0"]
build-backend = "poetry.core.masonry.api"
```

- [ ] **Step 2: Reinstall the environment**

```bash
poetry install
```

Expected: Resolves and installs `mcp`, `ccl_chromium_reader` (from `pylib/`), and `pytest`. No errors.

- [ ] **Step 3: Verify imports work**

```bash
poetry run python -c "from mcp.server.fastmcp import FastMCP; from ccl_chromium_reader import ccl_chromium_indexeddb; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add mcp, ccl_chromium_reader, pytest deps and new package/scripts"
```

---

## Task 2: Add `compute_display_names()` to TeamsExporter

**Files:**
- Modify: `teams_log_export/exporter.py:263` (after `build_user_map`)
- Create: `tests/__init__.py`
- Create: `tests/test_exporter_display_names.py`

- [ ] **Step 1: Write the failing test**

Create `tests/__init__.py` (empty):
```python
```

Create `tests/test_exporter_display_names.py`:

```python
from teams_log_export.exporter import TeamsExporter


def _exporter():
    return TeamsExporter("/fake")  # __init__ only sets paths, no I/O


def test_space_uses_space_topic():
    conversations = {
        "19:sp1@thread.skype": {
            "id": "19:sp1@thread.skype", "type": "Space",
            "topic": "", "spaceTopic": "Engineering",
            "teamId": "", "members": [],
        }
    }
    result = _exporter().compute_display_names(conversations, {}, {}, {})
    assert result["19:sp1@thread.skype"] == "Engineering"


def test_chat_uses_member_names():
    conversations = {
        "19:chat1@thread.skype": {
            "id": "19:chat1@thread.skype", "type": "Chat",
            "topic": "", "spaceTopic": "",
            "teamId": "", "members": ["u1", "u2"],
        }
    }
    result = _exporter().compute_display_names(
        conversations, {}, {"u1": "Alice", "u2": "Bob"}, {}
    )
    name = result["19:chat1@thread.skype"]
    assert "Alice" in name
    assert "Bob" in name


def test_channel_uses_channel_display_name():
    conversations = {
        "19:ch1@thread.skype": {
            "id": "19:ch1@thread.skype", "type": "Topic",
            "topic": "", "spaceTopic": "", "teamId": "", "members": [],
        }
    }
    channels = {"19:ch1@thread.skype": {"displayName": "General", "teamThreadId": ""}}
    result = _exporter().compute_display_names(conversations, channels, {}, {})
    assert result["19:ch1@thread.skype"] == "General"


def test_returns_all_conv_ids():
    conversations = {
        "a": {"id": "a", "type": "Chat", "topic": "", "spaceTopic": "", "teamId": "", "members": []},
        "b": {"id": "b", "type": "Space", "topic": "", "spaceTopic": "X", "teamId": "", "members": []},
    }
    result = _exporter().compute_display_names(conversations, {}, {}, {})
    assert set(result.keys()) == {"a", "b"}
```

- [ ] **Step 2: Run to verify it fails**

```bash
poetry run pytest tests/test_exporter_display_names.py -v
```

Expected: `AttributeError: 'TeamsExporter' object has no attribute 'compute_display_names'`

- [ ] **Step 3: Add `compute_display_names()` to `TeamsExporter`**

In `teams_log_export/exporter.py`, after the `build_user_map` method (after line 271), add:

```python
    def compute_display_names(
        self,
        conversations: dict[str, dict],
        channels: dict[str, dict],
        user_map: dict[str, str],
        messages_by_conv: dict[str, list[dict]],
    ) -> dict[str, str]:
        return {
            conv_id: self._conv_display_name(
                conv, channels, user_map, messages_by_conv.get(conv_id, [])
            )
            for conv_id, conv in conversations.items()
        }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
poetry run pytest tests/test_exporter_display_names.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add teams_log_export/exporter.py tests/__init__.py tests/test_exporter_display_names.py
git commit -m "feat: add TeamsExporter.compute_display_names()"
```

---

## Task 3: Implement `TeamsCache`

**Files:**
- Create: `teams_log_mcp/__init__.py`
- Create: `teams_log_mcp/cache.py`
- Create: `tests/conftest.py`
- Create: `tests/test_cache.py`

- [ ] **Step 1: Write the failing tests**

Create `teams_log_mcp/__init__.py` (empty):
```python
```

Create `tests/conftest.py`:

```python
import pytest

FIXTURE = {
    "channels": {
        "19:ch1@thread.skype": {
            "displayName": "General",
            "teamThreadId": "19:sp1@thread.skype",
        }
    },
    "conversations": {
        "19:sp1@thread.skype": {
            "id": "19:sp1@thread.skype", "type": "Space",
            "topic": "", "spaceTopic": "Engineering",
            "teamId": "", "members": [],
        },
        "19:chat1@thread.skype": {
            "id": "19:chat1@thread.skype", "type": "Chat",
            "topic": "", "spaceTopic": "",
            "teamId": "", "members": ["user:alice", "user:bob"],
        },
    },
    "messages_by_conv": {
        "19:sp1@thread.skype": [
            {
                "id": "m1", "conversationId": "19:sp1@thread.skype",
                "timestamp": "2024-01-15T10:00:00+00:00",
                "sender": "Alice", "senderId": "user:alice",
                "content": "Hello team, project update needed",
                "contentType": "text", "messageType": "RichText/Html",
                "threadType": "space", "parentMessageId": None,
            },
            {
                "id": "m2", "conversationId": "19:sp1@thread.skype",
                "timestamp": "2024-01-15T10:05:00+00:00",
                "sender": "Bob", "senderId": "user:bob",
                "content": "Hi Alice!",
                "contentType": "text", "messageType": "RichText/Html",
                "threadType": "space", "parentMessageId": None,
            },
        ],
        "19:chat1@thread.skype": [
            {
                "id": "m3", "conversationId": "19:chat1@thread.skype",
                "timestamp": "2024-01-16T09:00:00+00:00",
                "sender": "Alice", "senderId": "user:alice",
                "content": "Can we discuss the project?",
                "contentType": "text", "messageType": "RichText/Html",
                "threadType": "chat", "parentMessageId": None,
            },
        ],
    },
    "user_map": {"user:alice": "Alice", "user:bob": "Bob"},
    "display_names": {
        "19:sp1@thread.skype": "Engineering",
        "19:chat1@thread.skype": "Alice, Bob",
    },
}


@pytest.fixture
def fixture_data():
    return FIXTURE
```

Create `tests/test_cache.py`:

```python
from unittest.mock import MagicMock, patch
from tests.conftest import FIXTURE
from teams_log_mcp.cache import TeamsCache


def _mock_exporter():
    e = MagicMock()
    e.load_channel_names.return_value = dict(FIXTURE["channels"])
    e.load_conversations.return_value = {k: dict(v) for k, v in FIXTURE["conversations"].items()}
    e.load_messages.return_value = {
        k: [dict(m) for m in v] for k, v in FIXTURE["messages_by_conv"].items()
    }
    e.build_user_map.return_value = dict(FIXTURE["user_map"])
    e.compute_display_names.return_value = dict(FIXTURE["display_names"])
    return e


def test_loads_data_on_first_get():
    mock = _mock_exporter()
    with patch("teams_log_mcp.cache.TeamsExporter", return_value=mock):
        cache = TeamsCache("/fake")
        data = cache.get()
    assert "conversations" in data
    assert "messages_by_conv" in data
    assert "display_names" in data
    mock.load_channel_names.assert_called_once()


def test_does_not_reload_within_ttl():
    mock = _mock_exporter()
    with patch("teams_log_mcp.cache.TeamsExporter", return_value=mock):
        cache = TeamsCache("/fake")
        cache.get()
        cache.get()
    assert mock.load_channel_names.call_count == 1


def test_reloads_after_invalidate():
    mock = _mock_exporter()
    with patch("teams_log_mcp.cache.TeamsExporter", return_value=mock):
        cache = TeamsCache("/fake")
        cache.get()
        cache.invalidate()
        cache.get()
    assert mock.load_channel_names.call_count == 2


def test_reloads_when_stale():
    mock = _mock_exporter()
    with patch("teams_log_mcp.cache.TeamsExporter", return_value=mock):
        cache = TeamsCache("/fake")
        cache.get()
        cache._loaded_at = 0.0  # force stale by backdating timestamp
        cache.get()
    assert mock.load_channel_names.call_count == 2


def test_data_contains_expected_keys():
    mock = _mock_exporter()
    with patch("teams_log_mcp.cache.TeamsExporter", return_value=mock):
        cache = TeamsCache("/fake")
        data = cache.get()
    assert set(data.keys()) == {"channels", "conversations", "messages_by_conv", "user_map", "display_names"}
```

- [ ] **Step 2: Run to verify tests fail**

```bash
poetry run pytest tests/test_cache.py -v
```

Expected: `ModuleNotFoundError: No module named 'teams_log_mcp.cache'`

- [ ] **Step 3: Implement `teams_log_mcp/cache.py`**

```python
"""TTL-based in-memory cache for Teams data."""

from __future__ import annotations

import time

from teams_log_export.exporter import TeamsExporter

TTL_SECONDS = 300  # 5 minutes


class TeamsCache:
    def __init__(self, teams_root: str):
        self._exporter = TeamsExporter(teams_root)
        self._data: dict | None = None
        self._loaded_at: float = 0.0

    def _is_stale(self) -> bool:
        return self._data is None or (time.monotonic() - self._loaded_at) > TTL_SECONDS

    def _load(self) -> None:
        channels = self._exporter.load_channel_names()
        conversations = self._exporter.load_conversations()
        messages_by_conv = self._exporter.load_messages()
        user_map = self._exporter.build_user_map(messages_by_conv)

        for msgs in messages_by_conv.values():
            for m in msgs:
                if not m.get("sender") or m["sender"] == m.get("senderId"):
                    resolved = user_map.get(m.get("senderId") or "")
                    if resolved:
                        m["sender"] = resolved

        display_names = self._exporter.compute_display_names(
            conversations, channels, user_map, messages_by_conv
        )

        self._data = {
            "channels": channels,
            "conversations": conversations,
            "messages_by_conv": dict(messages_by_conv),
            "user_map": user_map,
            "display_names": display_names,
        }
        self._loaded_at = time.monotonic()

    def get(self) -> dict:
        if self._is_stale():
            self._load()
        return self._data

    def invalidate(self) -> None:
        """Force reload on next call."""
        self._loaded_at = 0.0
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
poetry run pytest tests/test_cache.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add teams_log_mcp/__init__.py teams_log_mcp/cache.py tests/conftest.py tests/test_cache.py
git commit -m "feat: add TeamsCache with 5-minute TTL"
```

---

## Task 4: Implement server scaffold and `list_conversations`

**Files:**
- Create: `teams_log_mcp/server.py`
- Create: `tests/test_server.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_server.py`:

```python
from unittest.mock import MagicMock
from tests.conftest import FIXTURE


def _cache():
    c = MagicMock()
    c.get.return_value = FIXTURE
    return c


# --- list_conversations ---

def test_list_conversations_includes_both_convs():
    from teams_log_mcp.server import _list_conversations
    result = _list_conversations(_cache())
    ids = [c["id"] for c in result["conversations"]]
    assert "19:sp1@thread.skype" in ids
    assert "19:chat1@thread.skype" in ids


def test_list_conversations_message_count():
    from teams_log_mcp.server import _list_conversations
    result = _list_conversations(_cache())
    eng = next(c for c in result["conversations"] if c["id"] == "19:sp1@thread.skype")
    assert eng["messageCount"] == 2
    assert eng["displayName"] == "Engineering"


def test_list_conversations_date_range():
    from teams_log_mcp.server import _list_conversations
    result = _list_conversations(_cache())
    eng = next(c for c in result["conversations"] if c["id"] == "19:sp1@thread.skype")
    assert eng["dateRange"]["first"] == "2024-01-15T10:00:00+00:00"
    assert eng["dateRange"]["last"] == "2024-01-15T10:05:00+00:00"
```

- [ ] **Step 2: Run to verify tests fail**

```bash
poetry run pytest tests/test_server.py -v
```

Expected: `ModuleNotFoundError: No module named 'teams_log_mcp.server'`

- [ ] **Step 3: Create `teams_log_mcp/server.py` with scaffold and `list_conversations`**

```python
"""MCP server exposing Teams conversation data."""

from __future__ import annotations

import os
import re

from mcp.server.fastmcp import FastMCP

from .cache import TeamsCache

mcp = FastMCP("teams-log", description="Access Microsoft Teams conversation history")
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
poetry run pytest tests/test_server.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add teams_log_mcp/server.py tests/test_server.py
git commit -m "feat: add MCP server scaffold and list_conversations tool"
```

---

## Task 5: Add `get_messages` tool

**Files:**
- Modify: `teams_log_mcp/server.py`
- Modify: `tests/test_server.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_server.py`:

```python
# --- get_messages ---

def test_find_conversation_id_exact():
    from teams_log_mcp.server import _find_conversation_id
    assert _find_conversation_id(FIXTURE, "19:sp1@thread.skype") == "19:sp1@thread.skype"


def test_find_conversation_id_substring():
    from teams_log_mcp.server import _find_conversation_id
    assert _find_conversation_id(FIXTURE, "engineering") == "19:sp1@thread.skype"


def test_find_conversation_id_not_found():
    from teams_log_mcp.server import _find_conversation_id
    assert _find_conversation_id(FIXTURE, "zzznope") is None


def test_get_messages_by_name_returns_note():
    from teams_log_mcp.server import _get_messages
    result = _get_messages(_cache(), "engineering")
    assert result["conversationId"] == "19:sp1@thread.skype"
    assert result["note"] == "Matched 'Engineering' for query 'engineering'"
    assert result["messageCount"] == 2


def test_get_messages_by_exact_id_no_note():
    from teams_log_mcp.server import _get_messages
    result = _get_messages(_cache(), "19:chat1@thread.skype")
    assert result["note"] is None
    assert result["messageCount"] == 1


def test_get_messages_limit():
    from teams_log_mcp.server import _get_messages
    result = _get_messages(_cache(), "engineering", limit=1)
    assert result["messageCount"] == 1
    assert result["messages"][0]["id"] == "m1"


def test_get_messages_after_filter():
    from teams_log_mcp.server import _get_messages
    result = _get_messages(_cache(), "engineering", after="2024-01-15T10:02:00+00:00")
    assert result["messageCount"] == 1
    assert result["messages"][0]["id"] == "m2"


def test_get_messages_before_filter():
    from teams_log_mcp.server import _get_messages
    result = _get_messages(_cache(), "engineering", before="2024-01-15T10:02:00+00:00")
    assert result["messageCount"] == 1
    assert result["messages"][0]["id"] == "m1"


def test_get_messages_not_found_returns_error():
    from teams_log_mcp.server import _get_messages
    result = _get_messages(_cache(), "zzznope")
    assert "error" in result


def test_get_messages_strips_html():
    from tests.conftest import FIXTURE as F
    import copy
    data = copy.deepcopy(F)
    data["messages_by_conv"]["19:sp1@thread.skype"][0]["content"] = "<p>Hello <b>team</b></p>"
    c = MagicMock()
    c.get.return_value = data
    from teams_log_mcp.server import _get_messages
    result = _get_messages(c, "19:sp1@thread.skype")
    assert result["messages"][0]["content"] == "Hello team"
```

- [ ] **Step 2: Run to verify new tests fail**

```bash
poetry run pytest tests/test_server.py -v
```

Expected: The 3 existing tests pass; the new 10 tests fail with `ImportError` or `TypeError`.

- [ ] **Step 3: Add `_get_messages` and `get_messages` to `teams_log_mcp/server.py`**

Add after the `list_conversations` tool:

```python
# --- get_messages ---

def _get_messages(
    cache: TeamsCache,
    conversation: str,
    limit: int = 100,
    before: str | None = None,
    after: str | None = None,
) -> dict:
    data = cache.get()
    conv_id = _find_conversation_id(data, conversation)
    if conv_id is None:
        return {"error": f"Conversation not found: {conversation!r}"}

    msgs = list(data["messages_by_conv"].get(conv_id, []))
    if after:
        msgs = [m for m in msgs if m.get("timestamp") and m["timestamp"] > after]
    if before:
        msgs = [m for m in msgs if m.get("timestamp") and m["timestamp"] < before]
    msgs = msgs[:min(limit, 500)]

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
```

- [ ] **Step 4: Run all tests to verify they pass**

```bash
poetry run pytest tests/test_server.py -v
```

Expected: 13 passed.

- [ ] **Step 5: Commit**

```bash
git add teams_log_mcp/server.py tests/test_server.py
git commit -m "feat: add get_messages tool"
```

---

## Task 6: Add `search_messages` tool

**Files:**
- Modify: `teams_log_mcp/server.py`
- Modify: `tests/test_server.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_server.py`:

```python
# --- search_messages ---

def test_search_finds_matches_across_convs():
    from teams_log_mcp.server import _search_messages
    result = _search_messages(_cache(), "project")
    ids = [r["id"] for r in result["results"]]
    assert "m1" in ids  # "project update needed" in Engineering
    assert "m3" in ids  # "discuss the project" in chat


def test_search_case_insensitive():
    from teams_log_mcp.server import _search_messages
    result = _search_messages(_cache(), "HELLO")
    assert result["resultCount"] == 1
    assert result["results"][0]["id"] == "m1"


def test_search_with_conversation_filter():
    from teams_log_mcp.server import _search_messages
    result = _search_messages(_cache(), "project", conversation="engineering")
    ids = [r["id"] for r in result["results"]]
    assert "m1" in ids
    assert "m3" not in ids


def test_search_result_includes_conversation_context():
    from teams_log_mcp.server import _search_messages
    result = _search_messages(_cache(), "Hello")
    assert result["results"][0]["conversationDisplayName"] == "Engineering"
    assert result["results"][0]["conversationType"] == "Space"


def test_search_no_results():
    from teams_log_mcp.server import _search_messages
    result = _search_messages(_cache(), "zzznomatch")
    assert result["resultCount"] == 0
    assert result["results"] == []


def test_search_limit():
    from teams_log_mcp.server import _search_messages
    result = _search_messages(_cache(), "a", limit=1)
    assert len(result["results"]) <= 1


def test_search_unknown_conversation_returns_error():
    from teams_log_mcp.server import _search_messages
    result = _search_messages(_cache(), "hello", conversation="zzznope")
    assert "error" in result
```

- [ ] **Step 2: Run to verify new tests fail**

```bash
poetry run pytest tests/test_server.py -v
```

Expected: 13 existing pass; 7 new fail with `ImportError`.

- [ ] **Step 3: Add `_search_messages` and `search_messages` to `teams_log_mcp/server.py`**

Add after the `get_messages` tool:

```python
# --- search_messages ---

def _search_messages(
    cache: TeamsCache,
    query: str,
    conversation: str | None = None,
    limit: int = 50,
) -> dict:
    data = cache.get()
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
            if query_lower in (msg.get("content") or "").lower():
                results.append({
                    **msg,
                    "content": _strip_html(msg.get("content") or ""),
                    "conversationDisplayName": display,
                    "conversationType": conv_type,
                })

    return {
        "query": query,
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
```

- [ ] **Step 4: Run all tests to verify they pass**

```bash
poetry run pytest tests/test_server.py -v
```

Expected: 20 passed.

- [ ] **Step 5: Commit**

```bash
git add teams_log_mcp/server.py tests/test_server.py
git commit -m "feat: add search_messages tool"
```

---

## Task 7: Add `get_conversation_summary` tool

**Files:**
- Modify: `teams_log_mcp/server.py`
- Modify: `tests/test_server.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_server.py`:

```python
# --- get_conversation_summary ---

def test_summary_returns_metadata():
    from teams_log_mcp.server import _get_conversation_summary
    result = _get_conversation_summary(_cache(), "engineering")
    assert result["conversationId"] == "19:sp1@thread.skype"
    assert result["displayName"] == "Engineering"
    assert result["type"] == "Space"
    assert result["messageCount"] == 2


def test_summary_includes_participants():
    from teams_log_mcp.server import _get_conversation_summary
    result = _get_conversation_summary(_cache(), "engineering")
    assert "Alice" in result["participants"]
    assert "Bob" in result["participants"]


def test_summary_date_range():
    from teams_log_mcp.server import _get_conversation_summary
    result = _get_conversation_summary(_cache(), "engineering")
    assert result["dateRange"]["first"] == "2024-01-15T10:00:00+00:00"
    assert result["dateRange"]["last"] == "2024-01-15T10:05:00+00:00"


def test_summary_recent_messages_max_5():
    from teams_log_mcp.server import _get_conversation_summary
    result = _get_conversation_summary(_cache(), "engineering")
    assert len(result["recentMessages"]) <= 5


def test_summary_includes_match_note():
    from teams_log_mcp.server import _get_conversation_summary
    result = _get_conversation_summary(_cache(), "engine")
    assert result["note"] is not None
    assert "Engineering" in result["note"]


def test_summary_not_found_returns_error():
    from teams_log_mcp.server import _get_conversation_summary
    result = _get_conversation_summary(_cache(), "zzznope")
    assert "error" in result
```

- [ ] **Step 2: Run to verify new tests fail**

```bash
poetry run pytest tests/test_server.py -v
```

Expected: 20 existing pass; 6 new fail.

- [ ] **Step 3: Add `_get_conversation_summary` and `get_conversation_summary` to `teams_log_mcp/server.py`**

Add after the `search_messages` tool:

```python
# --- get_conversation_summary ---

def _get_conversation_summary(cache: TeamsCache, conversation: str) -> dict:
    data = cache.get()
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
    """Get a summary of a Teams conversation: participants, message count, date range, and 5 most recent messages.

    Args:
        conversation: Conversation ID (exact) or display name (case-insensitive substring).
    """
    cache = _get_cache()
    if cache is None:
        return {"error": "TEAMS_ROOT not set. Check your extension configuration."}
    return _get_conversation_summary(cache, conversation)
```

- [ ] **Step 4: Run all tests to verify they pass**

```bash
poetry run pytest tests/test_server.py -v
```

Expected: 26 passed.

- [ ] **Step 5: Commit**

```bash
git add teams_log_mcp/server.py tests/test_server.py
git commit -m "feat: add get_conversation_summary tool"
```

---

## Task 8: Wire up entry point and integration smoke test

**Files:**
- Create: `teams_log_mcp/__main__.py`
- Create: `tests/test_integration.py`

- [ ] **Step 1: Create `teams_log_mcp/__main__.py`**

```python
from .server import mcp


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create `tests/test_integration.py`**

```python
import os
import pytest


@pytest.mark.skipif(not os.environ.get("TEAMS_ROOT"), reason="TEAMS_ROOT not set")
def test_smoke_load_from_real_db():
    from teams_log_mcp.cache import TeamsCache
    cache = TeamsCache(os.environ["TEAMS_ROOT"])
    data = cache.get()
    assert isinstance(data["conversations"], dict)
    assert isinstance(data["messages_by_conv"], dict)
    assert isinstance(data["display_names"], dict)
    total_msgs = sum(len(v) for v in data["messages_by_conv"].values())
    print(f"\nLoaded {len(data['conversations'])} conversations, {total_msgs} messages")
```

- [ ] **Step 3: Verify all unit tests still pass**

```bash
poetry run pytest tests/ -v --ignore=tests/test_integration.py
```

Expected: 26 passed (or more from all test files combined).

- [ ] **Step 4: Run integration test if TEAMS_ROOT is available**

```bash
TEAMS_ROOT="$(grep TEAMS_ROOT .env | cut -d= -f2)" poetry run pytest tests/test_integration.py -v -s
```

Expected: Either passes with a count of conversations/messages, or skips if TEAMS_ROOT is not found.

- [ ] **Step 5: Commit**

```bash
git add teams_log_mcp/__main__.py tests/test_integration.py
git commit -m "feat: add server entry point and integration smoke test"
```

---

## Task 9: Write `manifest.json`

**Files:**
- Create: `manifest.json`

- [ ] **Step 1: Create `manifest.json`**

```json
{
  "dxt_version": "0.1",
  "name": "teams-log",
  "display_name": "Microsoft Teams Log",
  "version": "0.1.0",
  "description": "Access your Microsoft Teams conversation history from Claude Desktop",
  "author": {
    "name": "Nicholas Avenell",
    "email": "nicholas@learningonscreen.ac.uk"
  },
  "server": {
    "type": "stdio",
    "command": "uv",
    "args": [
      "--directory",
      "${__dirname}",
      "run",
      "python",
      "-m",
      "teams_log_mcp"
    ],
    "env": {
      "TEAMS_ROOT": "${user_config.teams_root}"
    }
  },
  "user_config": {
    "teams_root": {
      "type": "string",
      "title": "Teams Data Path",
      "description": "Path to your Teams WV2Profile_tfw directory.\nWindows: C:\\Users\\<you>\\AppData\\Local\\Packages\\MSTeams_8wekyb3d8bbwe\\LocalCache\\Microsoft\\MSTeams\\EBWebView\\WV2Profile_tfw\nmacOS: ~/Library/Containers/com.microsoft.teams2/Data/Library/Application Support/Microsoft/MSTeams/EBWebView/WV2Profile_tfw",
      "required": true,
      "sensitive": false
    }
  },
  "tools": [
    {
      "name": "list_conversations",
      "description": "List all Teams chats, channels, and meetings with metadata"
    },
    {
      "name": "get_messages",
      "description": "Get messages from a conversation by name or ID"
    },
    {
      "name": "search_messages",
      "description": "Search for messages across all conversations"
    },
    {
      "name": "get_conversation_summary",
      "description": "Get a summary of a conversation including participants and recent messages"
    }
  ]
}
```

- [ ] **Step 2: Commit**

```bash
git add manifest.json
git commit -m "feat: add DXT manifest.json"
```

---

## Task 10: Write `build_dxt.py`, add Poetry script, and README

**Files:**
- Create: `build_dxt.py`
- Create: `README.md`

- [ ] **Step 1: Create `build_dxt.py`**

```python
#!/usr/bin/env python3
"""Build the teams-log.dxt Desktop Extension file."""
from __future__ import annotations

import pathlib
import zipfile

ROOT = pathlib.Path(__file__).parent
OUTPUT = ROOT / "teams-log.dxt"

INCLUDE = [
    "manifest.json",
    "pyproject.toml",
    "teams_log_mcp",
    "teams_log_export",
    "pylib/ccl_chromium_reader",
]

_SKIP_SUFFIXES = {".pyc"}
_SKIP_DIR_NAMES = {"__pycache__", ".git", ".egg-info"}


def _should_skip(path: pathlib.Path) -> bool:
    if path.suffix in _SKIP_SUFFIXES:
        return True
    return any(part in _SKIP_DIR_NAMES for part in path.parts)


def main() -> None:
    if OUTPUT.exists():
        OUTPUT.unlink()

    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in INCLUDE:
            path = ROOT / item
            if path.is_file():
                zf.write(path, item)
            elif path.is_dir():
                for f in sorted(path.rglob("*")):
                    if f.is_file() and not _should_skip(f):
                        zf.write(f, str(f.relative_to(ROOT)))
            else:
                print(f"Warning: {item!r} not found, skipping")

    size_kb = OUTPUT.stat().st_size / 1024
    print(f"Built {OUTPUT.name} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create `README.md`**

```markdown
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
```

- [ ] **Step 3: Build the DXT and verify it contains expected files**

```bash
poetry run build-dxt
```

Expected output: `Built teams-log.dxt (XXX.X KB)`

```bash
python -c "import zipfile; z=zipfile.ZipFile('teams-log.dxt'); names=z.namelist(); print('\n'.join(n for n in names if '/' not in n or n.count('/')==1))"
```

Expected: `manifest.json`, `pyproject.toml`, `teams_log_mcp/__init__.py`, `teams_log_mcp/cache.py`, `teams_log_mcp/server.py`, `teams_log_mcp/__main__.py`, and files from `teams_log_export/` and `pylib/ccl_chromium_reader/`.

- [ ] **Step 4: Run the full test suite one final time**

```bash
poetry run pytest tests/ --ignore=tests/test_integration.py -v
```

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add build_dxt.py README.md
git commit -m "feat: add build_dxt script and README with install instructions"
```

---

## Self-Review

**Spec coverage:**
- ✅ `teams_log_mcp/` module alongside `teams_log_export/` (Tasks 3–8)
- ✅ `TeamsCache` with 5-min TTL (Task 3)
- ✅ Four MCP tools (Tasks 4–7)
- ✅ Conversation lookup by exact ID or case-insensitive substring (Task 4, `_find_conversation_id`)
- ✅ HTML stripped on return (Task 5, `_strip_content`)
- ✅ Error messages for missing `TEAMS_ROOT` and unknown conversation (Tasks 4–7)
- ✅ Match note in response (Tasks 5, 7)
- ✅ Unit tests with fixtures, integration smoke test (Tasks 3–8)
- ✅ `manifest.json` with `TEAMS_ROOT` user config (Task 9)
- ✅ `build_dxt.py` + `build-dxt` script (Task 10)
- ✅ README with install steps (Task 10)

**Type consistency:** `TeamsCache.get()` returns a `dict` with keys `channels`, `conversations`, `messages_by_conv`, `user_map`, `display_names` — used consistently across Tasks 3–7. `_find_conversation_id` signature matches all callers.
