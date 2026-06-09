from unittest.mock import MagicMock, patch

from teams_log_mcp.cache import TeamsCache
from tests.conftest import FIXTURE


def _mock_exporter():
    e = MagicMock()
    e.load_channel_names.return_value = dict(FIXTURE["channels"])
    e.load_conversations.return_value = {
        k: dict(v) for k, v in FIXTURE["conversations"].items()
    }
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
