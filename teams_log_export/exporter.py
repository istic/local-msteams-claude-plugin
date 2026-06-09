"""Export Microsoft Teams chat and channel logs from local IndexedDB cache."""

from __future__ import annotations

import datetime
import json
import pathlib
import re
import sys
from collections import defaultdict
from typing import Any

from ccl_chromium_reader import ccl_chromium_indexeddb


def _safe_str(v: Any) -> Any:
    """Convert V8 Undefined and other special types to None for JSON."""
    if type(v).__name__ == "_Undefined":
        return None
    return v


class _TeamsJsonEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles non-standard types from IndexedDB."""

    def default(self, obj: Any) -> Any:
        if type(obj).__name__ == "_Undefined":
            return None
        if isinstance(obj, bytes):
            return obj.hex()
        if isinstance(obj, set):
            return list(obj)
        return str(obj)


def _ms_to_iso(ts: Any) -> str | None:
    """Convert a millisecond Unix timestamp to ISO 8601 string."""
    if ts is None:
        return None
    try:
        ts_float = float(ts)
        if ts_float <= 0:
            return None
        dt = datetime.datetime.fromtimestamp(
            ts_float / 1000.0, tz=datetime.timezone.utc
        )
        return dt.isoformat()
    except (ValueError, TypeError, OSError):
        return None


def _strip_html(html: str) -> str:
    """Strip HTML tags for plain text preview (content preserved as-is in JSON)."""
    if not html:
        return ""
    return re.sub(r"<[^>]+>", "", html).strip()


def _safe_filename(name: str) -> str:
    """Convert a string to a safe filename component."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = re.sub(r"\s+", " ", name).strip(" ._")
    return name[:120] or "unnamed"


class TeamsExporter:
    def __init__(self, teams_root: str | pathlib.Path):
        self.teams_root = pathlib.Path(teams_root)
        self._idb_base = self.teams_root / "IndexedDB"
        self._leveldb_path = (
            self._idb_base / "https_teams.microsoft.com_0.indexeddb.leveldb"
        )
        self._blob_path = self._idb_base / "https_teams.microsoft.com_0.indexeddb.blob"
        self._wrapper: ccl_chromium_indexeddb.WrappedIndexDB | None = None

    def _get_wrapper(self) -> ccl_chromium_indexeddb.WrappedIndexDB:
        if self._wrapper is None:
            self._wrapper = ccl_chromium_indexeddb.WrappedIndexDB(
                str(self._leveldb_path), str(self._blob_path)
            )
        return self._wrapper

    def _find_db(
        self, name_pattern: str
    ) -> list[ccl_chromium_indexeddb.WrappedDatabase]:
        """Return all databases whose name contains name_pattern."""
        wrapper = self._get_wrapper()
        matches = []
        for db_id in wrapper.database_ids:
            db = wrapper[db_id]
            if name_pattern in db.name:
                matches.append(db)
        return matches

    def _iter_store_records(
        self, db: ccl_chromium_indexeddb.WrappedDatabase, store_name: str
    ):
        """Yield (record.key, record.value, record.ldb_seq_no) for all live records."""
        try:
            store = db[store_name]
        except (KeyError, Exception):
            return
        for record in store.iterate_records(
            errors_to_stdout=False,
            bad_deserializer_data_handler=lambda k, v: None,
        ):
            if not record.is_live:
                continue
            yield record

    # ------------------------------------------------------------------
    # Channel info: thread_id -> {displayName, teamThreadId}
    # ------------------------------------------------------------------

    def load_channel_names(self) -> dict[str, dict]:
        channels: dict[str, dict] = {}
        for db in self._find_db("get-all-channels-manager"):
            for record in self._iter_store_records(
                db, "get-all-channels-manager-cache-store"
            ):
                val = record.value
                if not isinstance(val, dict):
                    continue
                thread_id = _safe_str(val.get("threadId")) or str(record.key)
                display_name = _safe_str(val.get("displayName")) or ""
                team_thread_id = _safe_str(val.get("teamThreadId")) or ""
                if thread_id and thread_id not in channels:
                    channels[thread_id] = {
                        "displayName": display_name,
                        "teamThreadId": team_thread_id,
                    }
        return channels

    # ------------------------------------------------------------------
    # Conversation metadata: conv_id -> {type, displayName, teamId, members, ...}
    # ------------------------------------------------------------------

    def load_conversations(self) -> dict[str, dict]:
        convs: dict[str, dict] = {}
        # Track ldb_seq_no to keep the latest version
        conv_seqno: dict[str, int] = {}

        for db in self._find_db("conversation-manager"):
            for record in self._iter_store_records(db, "conversations"):
                val = record.value
                if not isinstance(val, dict):
                    continue
                conv_id = _safe_str(val.get("id")) or str(record.key)
                if not conv_id:
                    continue
                seqno = record.ldb_seq_no or 0
                if conv_id in conv_seqno and conv_seqno[conv_id] >= seqno:
                    continue
                conv_seqno[conv_id] = seqno

                tp = val.get("threadProperties") or {}
                if not isinstance(tp, dict):
                    tp = {}

                topic = _safe_str(tp.get("topic")) or ""
                space_topic = _safe_str(tp.get("spaceThreadTopic")) or ""
                conv_type = _safe_str(val.get("type")) or "Unknown"
                team_id = _safe_str(val.get("teamId")) or ""

                members = []
                raw_members = val.get("members") or []
                if isinstance(raw_members, list):
                    for m in raw_members:
                        if isinstance(m, dict):
                            mid = _safe_str(m.get("id")) or ""
                            if mid:
                                members.append(mid)

                convs[conv_id] = {
                    "id": conv_id,
                    "type": conv_type,
                    "topic": topic,
                    "spaceTopic": space_topic,
                    "teamId": team_id,
                    "members": members,
                }
        return convs

    # ------------------------------------------------------------------
    # Messages: conv_id -> list[message_dict]
    # ------------------------------------------------------------------

    def load_messages(self) -> dict[str, list[dict]]:
        """Load all messages from replychains, deduplicated by (conv_id, msg_id)."""
        # (conv_id, msg_id) -> (seqno, message_dict)
        msg_map: dict[tuple[str, str], tuple[int, dict]] = {}

        for db in self._find_db("replychain-manager"):
            # skip metadata-only databases
            if "replychain-metadata-manager" in db.name:
                continue
            if "streams-replychain-manager" in db.name:
                continue
            for record in self._iter_store_records(db, "replychains"):
                val = record.value
                if not isinstance(val, dict):
                    continue
                conv_id = _safe_str(val.get("conversationId")) or ""
                if not conv_id:
                    continue
                seqno = record.ldb_seq_no or 0
                mm = val.get("messageMap") or {}
                if not isinstance(mm, dict):
                    continue
                for mk, mv in mm.items():
                    if not isinstance(mv, dict):
                        continue
                    msg_id = str(_safe_str(mv.get("id")) or mk)
                    key = (conv_id, msg_id)
                    if key not in msg_map or msg_map[key][0] < seqno:
                        msg_map[key] = (seqno, mv)

        # Group by conversation, extract relevant fields
        by_conv: dict[str, list[dict]] = defaultdict(list)
        for (conv_id, msg_id), (_, mv) in msg_map.items():
            msg = self._extract_message(mv, conv_id)
            if msg:
                by_conv[conv_id].append(msg)

        # Sort each conversation's messages by timestamp
        for conv_id in by_conv:
            by_conv[conv_id].sort(key=lambda m: m.get("timestamp") or "")

        return dict(by_conv)

    def _extract_message(self, mv: dict, conv_id: str) -> dict | None:
        msg_id = str(_safe_str(mv.get("id")) or "")
        msg_type = _safe_str(mv.get("messageType")) or ""
        content_type = _safe_str(mv.get("contentType")) or ""
        content = _safe_str(mv.get("content")) or ""
        creator = _safe_str(mv.get("creator")) or ""
        sender = (
            _safe_str(mv.get("imDisplayName"))
            or _safe_str(mv.get("fromDisplayNameInToken"))
            or _safe_str(mv.get("fromGivenNameInToken"))
            or creator
        )
        # Strip empty/whitespace
        if not isinstance(sender, str):
            sender = ""
        sender = sender.strip()

        arrival_ts = _safe_str(mv.get("originalArrivalTime"))
        timestamp = _ms_to_iso(arrival_ts)

        parent_id = _safe_str(mv.get("parentMessageId")) or ""
        thread_type = _safe_str(mv.get("threadType")) or ""

        return {
            "id": msg_id,
            "conversationId": conv_id,
            "timestamp": timestamp,
            "sender": sender,
            "senderId": creator,
            "content": content,
            "contentType": content_type,
            "messageType": msg_type,
            "threadType": thread_type,
            "parentMessageId": parent_id if parent_id != msg_id else None,
        }

    # ------------------------------------------------------------------
    # User display name map: creator_id -> display_name (from messages)
    # ------------------------------------------------------------------

    def build_user_map(self, messages_by_conv: dict[str, list[dict]]) -> dict[str, str]:
        user_map: dict[str, str] = {}
        for msgs in messages_by_conv.values():
            for m in msgs:
                uid = m.get("senderId") or ""
                name = m.get("sender") or ""
                if uid and name and uid not in user_map:
                    user_map[uid] = name
        return user_map

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

    # ------------------------------------------------------------------
    # Determine display name for a conversation
    # ------------------------------------------------------------------

    def _conv_display_name(
        self,
        conv: dict,
        channels: dict[str, dict],
        user_map: dict[str, str],
        messages: list[dict],
    ) -> str:
        conv_id = conv["id"]
        conv_type = conv["type"]

        # Use topic/space topic if set
        topic = conv.get("spaceTopic") or conv.get("topic") or ""
        if topic:
            return topic

        # For channels, use the channel display name
        if conv_id in channels:
            return channels[conv_id]["displayName"]

        # For chats, build from member names
        if conv_type in ("Chat",):
            member_ids = conv.get("members") or []
            names = [user_map.get(mid, "") for mid in member_ids if user_map.get(mid)]
            if names:
                return ", ".join(names)
            # Fall back to sender names from messages
            senders = []
            seen_senders: set[str] = set()
            for m in messages[:20]:
                s = m.get("sender") or ""
                if s and s not in seen_senders:
                    senders.append(s)
                    seen_senders.add(s)
            if senders:
                return ", ".join(senders)

        return conv_id

    # ------------------------------------------------------------------
    # Main export
    # ------------------------------------------------------------------

    def export(self, output_dir: str | pathlib.Path, verbose: bool = True) -> None:
        output_dir = pathlib.Path(output_dir)

        if verbose:
            print("Loading channel names...", file=sys.stderr)
        channels = self.load_channel_names()

        if verbose:
            print("Loading conversation metadata...", file=sys.stderr)
        conversations = self.load_conversations()

        if verbose:
            print("Loading messages...", file=sys.stderr)
        messages_by_conv = self.load_messages()

        if verbose:
            print(
                f"Found {len(conversations)} conversations, "
                f"{sum(len(v) for v in messages_by_conv.values())} messages",
                file=sys.stderr,
            )

        user_map = self.build_user_map(messages_by_conv)

        # Second pass: resolve sender names where sender == senderId
        for msgs in messages_by_conv.values():
            for m in msgs:
                if not m.get("sender") or m["sender"] == m.get("senderId"):
                    resolved = user_map.get(m.get("senderId") or "")
                    if resolved:
                        m["sender"] = resolved

        # Build team name map: team_thread_id -> space_topic
        team_names: dict[str, str] = {}
        for conv in conversations.values():
            if conv["type"] == "Space" and conv.get("spaceTopic"):
                team_names[conv["id"]] = conv["spaceTopic"]

        exported_at = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        total_written = 0

        for conv_id, messages in messages_by_conv.items():
            if not messages:
                continue

            conv = conversations.get(
                conv_id,
                {
                    "id": conv_id,
                    "type": "Unknown",
                    "topic": "",
                    "spaceTopic": "",
                    "teamId": "",
                    "members": [],
                },
            )
            conv_type = conv.get("type", "Unknown")

            display_name = self._conv_display_name(conv, channels, user_map, messages)

            # Determine output subdirectory
            if conv_type in ("Topic",) or (conv_id in channels):
                # Channel (topic in a team)
                team_id = (
                    conv.get("teamId")
                    or channels.get(conv_id, {}).get("teamThreadId")
                    or ""
                )
                team_name = team_names.get(team_id) or "Unknown Team"
                subdir = output_dir / "channels" / _safe_filename(team_name)
                channel_name = (
                    channels.get(conv_id, {}).get("displayName") or display_name
                )
            elif conv_type == "Space":
                # The General channel of a team
                team_id = conv_id
                team_name = team_names.get(team_id) or display_name
                subdir = output_dir / "channels" / _safe_filename(team_name)
                channel_name = "General"
                display_name = "General"
            elif conv_type == "Meeting":
                subdir = output_dir / "meetings"
                channel_name = None
            elif conv_type in ("Chat",):
                subdir = output_dir / "chats"
                channel_name = None
            elif conv_type == "Thread":
                subdir = output_dir / "threads"
                channel_name = None
            else:
                subdir = output_dir / "other"
                channel_name = None

            subdir.mkdir(parents=True, exist_ok=True)
            filename = _safe_filename(display_name) + ".json"
            out_path = subdir / filename

            # If file already exists (name collision), append conv_id suffix
            if out_path.exists():
                short_id = conv_id.replace("@", "_").replace(":", "_")[-20:]
                filename = _safe_filename(display_name) + f"_{short_id}.json"
                out_path = subdir / filename

            output = {
                "id": conv_id,
                "type": conv_type,
                "displayName": display_name,
                "exportedAt": exported_at,
                "messageCount": len(messages),
                "messages": messages,
            }
            if channel_name:
                output["channelName"] = channel_name

            out_path.write_text(
                json.dumps(output, indent=2, ensure_ascii=False, cls=_TeamsJsonEncoder),
                encoding="utf-8",
            )
            total_written += 1
            if verbose:
                print(
                    f"  {out_path.relative_to(output_dir)} ({len(messages)} messages)",
                    file=sys.stderr,
                )

        if verbose:
            print(
                f"\nExported {total_written} conversations to {output_dir}",
                file=sys.stderr,
            )
