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
    import copy
    from unittest.mock import MagicMock
    from tests.conftest import FIXTURE as F
    data = copy.deepcopy(F)
    data["messages_by_conv"]["19:sp1@thread.skype"][0]["content"] = "<p>Hello <b>team</b></p>"
    c = MagicMock()
    c.get.return_value = data
    from teams_log_mcp.server import _get_messages
    result = _get_messages(c, "19:sp1@thread.skype")
    assert result["messages"][0]["content"] == "Hello team"


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
