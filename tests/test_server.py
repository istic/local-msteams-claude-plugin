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
