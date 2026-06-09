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
