from unittest.mock import MagicMock, patch

from teams_log_mcp.cache import TeamsCache
from tests.conftest import FIXTURE


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
    assert set(data.keys()) == {
        "channels",
        "conversations",
        "messages_by_conv",
        "user_map",
        "display_names",
    }


# --- error handling ---


def test_load_failure_returns_error_sentinel():
    mock = _mock_exporter()
    mock.load_channel_names.side_effect = ValueError("corrupted DB")
    with patch("teams_log_mcp.cache.TeamsExporter", return_value=mock):
        cache = TeamsCache("/fake")
        data = cache.get()
    assert "error" in data
    assert "corrupted DB" in data["error"]


def test_load_resolves_sender_name_from_user_map():
    mock = _mock_exporter()
    # Message where sender field equals the raw senderId — should be resolved
    messages = {
        "conv1": [
            {
                "id": "m1",
                "conversationId": "conv1",
                "timestamp": "2024-01-01T00:00:00+00:00",
                "sender": "8:orgid:abc123",  # raw ID, not a display name
                "senderId": "8:orgid:abc123",
                "content": "hi",
                "contentType": "text",
                "messageType": "RichText/Html",
                "threadType": "",
                "parentMessageId": None,
            }
        ]
    }
    mock.load_messages.return_value = messages
    mock.build_user_map.return_value = {"8:orgid:abc123": "Alice"}
    mock.compute_display_names.return_value = {"conv1": "conv1"}
    with patch("teams_log_mcp.cache.TeamsExporter", return_value=mock):
        cache = TeamsCache("/fake")
        data = cache.get()
    assert data["messages_by_conv"]["conv1"][0]["sender"] == "Alice"


def test_error_is_not_cached_retries_next_call():
    mock = _mock_exporter()
    # First call raises, second succeeds
    mock.load_channel_names.side_effect = [
        ValueError("oops"),
        dict(FIXTURE["channels"]),
    ]
    with patch("teams_log_mcp.cache.TeamsExporter", return_value=mock):
        cache = TeamsCache("/fake")
        first = cache.get()
        second = cache.get()
    assert "error" in first
    assert "error" not in second
    assert "conversations" in second
