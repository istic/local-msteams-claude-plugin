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
