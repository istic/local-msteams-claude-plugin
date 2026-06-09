from teams_log_export.exporter import TeamsExporter


def _exporter():
    return TeamsExporter("/fake")  # __init__ only sets paths, no I/O


def test_space_uses_space_topic():
    conversations = {
        "19:sp1@thread.skype": {
            "id": "19:sp1@thread.skype",
            "type": "Space",
            "topic": "",
            "spaceTopic": "Engineering",
            "teamId": "",
            "members": [],
        }
    }
    result = _exporter().compute_display_names(conversations, {}, {}, {})
    assert result["19:sp1@thread.skype"] == "Engineering"


def test_chat_uses_member_names():
    conversations = {
        "19:chat1@thread.skype": {
            "id": "19:chat1@thread.skype",
            "type": "Chat",
            "topic": "",
            "spaceTopic": "",
            "teamId": "",
            "members": ["u1", "u2"],
        }
    }
    result = _exporter().compute_display_names(conversations, {}, {"u1": "Alice", "u2": "Bob"}, {})
    name = result["19:chat1@thread.skype"]
    assert "Alice" in name
    assert "Bob" in name


def test_channel_uses_channel_display_name():
    conversations = {
        "19:ch1@thread.skype": {
            "id": "19:ch1@thread.skype",
            "type": "Topic",
            "topic": "",
            "spaceTopic": "",
            "teamId": "",
            "members": [],
        }
    }
    channels = {"19:ch1@thread.skype": {"displayName": "General", "teamThreadId": ""}}
    result = _exporter().compute_display_names(conversations, channels, {}, {})
    assert result["19:ch1@thread.skype"] == "General"


def test_returns_all_conv_ids():
    conversations = {
        "a": {
            "id": "a",
            "type": "Chat",
            "topic": "",
            "spaceTopic": "",
            "teamId": "",
            "members": [],
        },
        "b": {
            "id": "b",
            "type": "Space",
            "topic": "",
            "spaceTopic": "X",
            "teamId": "",
            "members": [],
        },
    }
    result = _exporter().compute_display_names(conversations, {}, {}, {})
    assert set(result.keys()) == {"a", "b"}
