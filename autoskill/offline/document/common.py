"""
Common helpers for the offline document pipeline.

These utilities intentionally stay small and dependency-free so stage modules
can share the same naming and behavior without reimplementing the same text and
logging helpers.
"""

from __future__ import annotations

import re
from typing import Callable, Iterable, List, Optional

StageLogger = Optional[Callable[[str], None]]


def emit_stage_log(logger: StageLogger, message: str) -> None:
    """Emits one stage log line when a logger callback is configured."""

    if logger is not None:
        logger(str(message))


def normalize_text(text: str, *, lower: bool = False) -> str:
    """Collapses whitespace while preserving token order."""

    normalized = re.sub(r"\s+", " ", str(text or "").strip())
    return normalized.lower() if lower else normalized


def dedupe_strings(
    items: Iterable[str],
    *,
    lower: bool = True,
) -> List[str]:
    """Deduplicates strings while preserving their first-seen order."""

    out: List[str] = []
    seen = set()
    for item in items:
        value = str(item or "").strip()
        if not value:
            continue
        key = normalize_text(value, lower=lower)
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out
