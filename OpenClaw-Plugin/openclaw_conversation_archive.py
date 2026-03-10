"""
Persist OpenClaw conversation payloads locally for future replay/offline processing.

The archive is intentionally append-only and JSONL-based so it stays lightweight,
easy to inspect, and independent from the AutoSkill core store implementation.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _slug(value: Any, *, fallback: str) -> str:
    raw = _safe_text(value)
    if not raw:
        return fallback
    out: List[str] = []
    prev_dash = False
    for ch in raw:
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
            continue
        if ch in {"-", "_", ".", ":"}:
            out.append(ch)
            prev_dash = False
            continue
        if ch.isspace():
            if not prev_dash:
                out.append("-")
                prev_dash = True
    text = "".join(out).strip("-_.:") or fallback
    return text[:96] or fallback


def detect_archive_dir(explicit_path: str = "") -> str:
    explicit = _safe_text(explicit_path)
    if explicit:
        return str(Path(explicit).expanduser().resolve())
    return str((Path.home() / ".openclaw" / "autoskill" / "conversations").resolve())


def _sanitize_message(message: Any, *, max_content_chars: int) -> Optional[Dict[str, Any]]:
    if not isinstance(message, dict):
        return None
    role = _safe_text(message.get("role")).lower()
    if not role:
        return None
    content = message.get("content")
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = _safe_text(item.get("text") or item.get("content"))
                if text:
                    parts.append(text)
        content_text = "".join(parts)
    else:
        content_text = _safe_text(content)
    if max_content_chars > 0 and len(content_text) > max_content_chars:
        content_text = content_text[:max_content_chars]
    out: Dict[str, Any] = {
        "role": role,
        "content": content_text,
    }
    name = _safe_text(message.get("name"))
    if name:
        out["name"] = name[:128]
    tool_call_id = _safe_text(message.get("tool_call_id"))
    if tool_call_id:
        out["tool_call_id"] = tool_call_id[:128]
    return out


def _sanitize_messages(
    messages: List[Dict[str, Any]],
    *,
    max_messages: int,
    max_content_chars: int,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for item in list(messages or [])[: max(1, int(max_messages or 200))]:
        sanitized = _sanitize_message(item, max_content_chars=max_content_chars)
        if sanitized is not None:
            out.append(sanitized)
    return out


def _sanitize_metadata(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    raw = metadata if isinstance(metadata, dict) else {}
    out: Dict[str, Any] = {}
    for key, value in raw.items():
        k = _safe_text(key)
        if not k:
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            out[k] = value
            continue
        if isinstance(value, dict):
            nested: Dict[str, Any] = {}
            for nk, nv in value.items():
                nnk = _safe_text(nk)
                if not nnk:
                    continue
                if isinstance(nv, (str, int, float, bool)) or nv is None:
                    nested[nnk] = nv
            if nested:
                out[k] = nested
            continue
        if isinstance(value, list):
            items = [item for item in value if isinstance(item, (str, int, float, bool)) or item is None]
            if items:
                out[k] = items
    return out


@dataclass
class OpenClawConversationArchiveConfig:
    enabled: bool = True
    archive_dir: str = ""
    max_messages_per_record: int = 200
    max_content_chars: int = 20000

    def normalize(self) -> "OpenClawConversationArchiveConfig":
        self.enabled = bool(self.enabled)
        self.archive_dir = detect_archive_dir(self.archive_dir)
        self.max_messages_per_record = max(1, int(self.max_messages_per_record or 200))
        self.max_content_chars = max(256, int(self.max_content_chars or 20000))
        return self


class OpenClawConversationArchive:
    """Append OpenClaw conversation payloads into local JSONL files."""

    def __init__(self, *, config: Optional[OpenClawConversationArchiveConfig] = None) -> None:
        self.config = (config or OpenClawConversationArchiveConfig()).normalize()
        self._lock = threading.Lock()

    def status(self) -> Dict[str, Any]:
        return {
            "enabled": bool(self.config.enabled),
            "archive_dir": str(self.config.archive_dir),
            "max_messages_per_record": int(self.config.max_messages_per_record),
            "max_content_chars": int(self.config.max_content_chars),
        }

    def append_record(
        self,
        *,
        user_id: str,
        source: str,
        messages: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        uid = _safe_text(user_id)
        if not self.config.enabled:
            return {"enabled": False, "skipped": True, "reason": "archive_disabled", "user_id": uid}
        sanitized_messages = _sanitize_messages(
            list(messages or []),
            max_messages=int(self.config.max_messages_per_record),
            max_content_chars=int(self.config.max_content_chars),
        )
        if not sanitized_messages:
            return {"enabled": True, "skipped": True, "reason": "empty_messages", "user_id": uid}

        root = Path(self.config.archive_dir).expanduser().resolve()
        bucket = root / _slug(uid or "default", fallback="default")
        bucket.mkdir(parents=True, exist_ok=True)
        day = time.strftime("%Y-%m-%d", time.localtime())
        path = bucket / f"{day}.jsonl"
        payload = {
            "record_id": uuid.uuid4().hex,
            "event_time": int(time.time() * 1000),
            "user_id": uid,
            "source": _safe_text(source) or "openclaw",
            "message_count": len(sanitized_messages),
            "messages": sanitized_messages,
            "metadata": _sanitize_metadata(metadata),
        }
        line = json.dumps(payload, ensure_ascii=False) + "\n"
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line)
        return {
            "enabled": True,
            "skipped": False,
            "reason": "",
            "user_id": uid,
            "path": str(path),
            "record_id": str(payload["record_id"]),
        }
