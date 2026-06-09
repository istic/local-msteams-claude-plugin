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
            "id": "19:sp1@thread.skype",
            "type": "Space",
            "topic": "",
            "spaceTopic": "Engineering",
            "teamId": "",
            "members": [],
        },
        "19:chat1@thread.skype": {
            "id": "19:chat1@thread.skype",
            "type": "Chat",
            "topic": "",
            "spaceTopic": "",
            "teamId": "",
            "members": ["user:alice", "user:bob"],
        },
    },
    "messages_by_conv": {
        "19:sp1@thread.skype": [
            {
                "id": "m1",
                "conversationId": "19:sp1@thread.skype",
                "timestamp": "2024-01-15T10:00:00+00:00",
                "sender": "Alice",
                "senderId": "user:alice",
                "content": "Hello team, project update needed",
                "contentType": "text",
                "messageType": "RichText/Html",
                "threadType": "space",
                "parentMessageId": None,
            },
            {
                "id": "m2",
                "conversationId": "19:sp1@thread.skype",
                "timestamp": "2024-01-15T10:05:00+00:00",
                "sender": "Bob",
                "senderId": "user:bob",
                "content": "Hi Alice!",
                "contentType": "text",
                "messageType": "RichText/Html",
                "threadType": "space",
                "parentMessageId": None,
            },
        ],
        "19:chat1@thread.skype": [
            {
                "id": "m3",
                "conversationId": "19:chat1@thread.skype",
                "timestamp": "2024-01-16T09:00:00+00:00",
                "sender": "Alice",
                "senderId": "user:alice",
                "content": "Can we discuss the project?",
                "contentType": "text",
                "messageType": "RichText/Html",
                "threadType": "chat",
                "parentMessageId": None,
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
