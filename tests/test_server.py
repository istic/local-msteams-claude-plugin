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

    assert (
        _find_conversation_id(FIXTURE, "19:sp1@thread.skype") == "19:sp1@thread.skype"
    )


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
    data["messages_by_conv"]["19:sp1@thread.skype"][0][
        "content"
    ] = "<p>Hello <b>team</b></p>"
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


def test_search_does_not_match_html_tags():
    import copy
    from unittest.mock import MagicMock

    from tests.conftest import FIXTURE as F

    data = copy.deepcopy(F)
    data["messages_by_conv"]["19:sp1@thread.skype"][0][
        "content"
    ] = '<p class="msg">Hello</p>'
    c = MagicMock()
    c.get.return_value = data
    from teams_log_mcp.server import _search_messages

    result = _search_messages(c, "class")
    assert result["resultCount"] == 0  # should not match HTML attributes


def test_search_total_count_field():
    from teams_log_mcp.server import _search_messages

    result = _search_messages(_cache(), "project")
    assert "totalCount" in result
    assert result["totalCount"] >= result["resultCount"]


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


# --- _strip_html ---


def test_strip_html_handles_bytes():
    from teams_log_mcp.server import _strip_html

    assert _strip_html(b"<p>Hello <b>world</b></p>") == "Hello world"


def test_strip_html_handles_empty_bytes():
    from teams_log_mcp.server import _strip_html

    assert _strip_html(b"") == ""


# --- _default_teams_root ---


def test_default_teams_root_macos_hardcoded_path(tmp_path):
    import pathlib
    from unittest.mock import patch

    from teams_log_mcp.server import _default_teams_root

    profile = (
        tmp_path
        / "Library/Containers/com.microsoft.teams2/Data/Library"
        / "Application Support/Microsoft/MSTeams/EBWebView/WV2Profile_tfw"
    )
    profile.mkdir(parents=True)
    with (
        patch("platform.system", return_value="Darwin"),
        patch("pathlib.Path.home", return_value=tmp_path),
    ):
        result = _default_teams_root()
    assert pathlib.Path(result) == profile


def test_default_teams_root_macos_fallback_glob(tmp_path):
    import pathlib
    from unittest.mock import patch

    from teams_log_mcp.server import _default_teams_root

    # Different container name — hardcoded path won't exist
    profile = (
        tmp_path
        / "Library/Containers/com.microsoft.teams-alt/Data/Library"
        / "Application Support/Microsoft/MSTeams/EBWebView/WV2Profile_tfw"
    )
    profile.mkdir(parents=True)
    with (
        patch("platform.system", return_value="Darwin"),
        patch("pathlib.Path.home", return_value=tmp_path),
    ):
        result = _default_teams_root()
    assert pathlib.Path(result) == profile


def test_default_teams_root_macos_not_found(tmp_path):
    from unittest.mock import patch

    from teams_log_mcp.server import _default_teams_root

    with (
        patch("platform.system", return_value="Darwin"),
        patch("pathlib.Path.home", return_value=tmp_path),
    ):
        result = _default_teams_root()
    assert result == ""


def test_default_teams_root_windows_hardcoded_path(tmp_path):
    import os
    import pathlib
    from unittest.mock import patch

    from teams_log_mcp.server import _default_teams_root

    profile = (
        tmp_path
        / "Packages/MSTeams_8wekyb3d8bbwe/LocalCache"
        / "Microsoft/MSTeams/EBWebView/WV2Profile_tfw"
    )
    profile.mkdir(parents=True)
    with (
        patch("platform.system", return_value="Windows"),
        patch.dict(os.environ, {"LOCALAPPDATA": str(tmp_path)}),
    ):
        result = _default_teams_root()
    assert pathlib.Path(result) == profile


def test_default_teams_root_windows_fallback_glob(tmp_path):
    import os
    import pathlib
    from unittest.mock import patch

    from teams_log_mcp.server import _default_teams_root

    # Different package string — hardcoded path won't exist
    profile = (
        tmp_path
        / "Packages/MSTeams_newstring123/LocalCache"
        / "Microsoft/MSTeams/EBWebView/WV2Profile_tfw"
    )
    profile.mkdir(parents=True)
    with (
        patch("platform.system", return_value="Windows"),
        patch.dict(os.environ, {"LOCALAPPDATA": str(tmp_path)}),
    ):
        result = _default_teams_root()
    assert pathlib.Path(result) == profile


def test_default_teams_root_windows_no_localappdata():
    import os
    from unittest.mock import patch

    from teams_log_mcp.server import _default_teams_root

    with (
        patch("platform.system", return_value="Windows"),
        patch.dict(os.environ, {"LOCALAPPDATA": ""}),
    ):
        assert _default_teams_root() == ""


def test_default_teams_root_unknown_os():
    from unittest.mock import patch

    from teams_log_mcp.server import _default_teams_root

    with patch("platform.system", return_value="Linux"):
        assert _default_teams_root() == ""


# --- cache error propagation ---

_ERROR_DATA = {
    "error": "DB load failed",
    "conversations": {},
    "messages_by_conv": {},
    "display_names": {},
    "channels": {},
    "user_map": {},
}


def _error_cache():
    c = MagicMock()
    c.get.return_value = _ERROR_DATA
    return c


def test_list_conversations_propagates_cache_error():
    from teams_log_mcp.server import _list_conversations

    result = _list_conversations(_error_cache())
    assert "error" in result
    assert "DB load failed" in result["error"]


def test_get_messages_propagates_cache_error():
    from teams_log_mcp.server import _get_messages

    result = _get_messages(_error_cache(), "anything")
    assert "error" in result
    assert "DB load failed" in result["error"]


def test_search_messages_propagates_cache_error():
    from teams_log_mcp.server import _search_messages

    result = _search_messages(_error_cache(), "anything")
    assert "error" in result
    assert "DB load failed" in result["error"]


def test_get_conversation_summary_propagates_cache_error():
    from teams_log_mcp.server import _get_conversation_summary

    result = _get_conversation_summary(_error_cache(), "anything")
    assert "error" in result
    assert "DB load failed" in result["error"]
