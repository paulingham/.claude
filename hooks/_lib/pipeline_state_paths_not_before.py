"""Slice slice-c-consumer carryforward — `not_before` frontmatter filter.

A pipeline-state file may carry a `not_before: <ISO 8601>` frontmatter field
that gates when SessionStart's active-pipeline scan surfaces it. The helper
here parses the field and answers a single question: is the file ready to
appear in the active list at `now_unix`?

Fail-open: malformed or missing `not_before` returns True (file IS active).
The slice-d soak placeholder is the canonical caller — it sets
`not_before: 2026-08-08T00:00:00Z` so SessionStart does not re-enter
`/pipeline-resume` for a pipeline that is not yet ready.
"""
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _parse_iso8601_to_unix(value: str) -> Optional[float]:
    """Parse an ISO 8601 timestamp; return unix seconds or None on failure."""
    text = value.strip()
    if not text:
        return None
    # `fromisoformat` accepts `Z` natively in Python 3.11+; normalise for older
    # Pythons and for the canonical `2026-08-08T00:00:00Z` form.
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _read_not_before(path: Path) -> Optional[str]:
    """Return the raw `not_before` frontmatter value, or None if absent."""
    try:
        text = path.read_text()
    except (OSError, UnicodeDecodeError):
        return None
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    front = text[3:end]
    for line in front.splitlines():
        stripped = line.strip()
        if stripped.startswith("not_before:"):
            return stripped.split(":", 1)[1].strip()
    return None


def is_active(path: Path, now_unix: float) -> bool:
    """Return True iff the file is ready to surface at `now_unix`.

    Fail-open: missing or malformed `not_before` → True.
    """
    raw = _read_not_before(path)
    if raw is None:
        return True
    parsed = _parse_iso8601_to_unix(raw)
    if parsed is None:
        return True
    return now_unix >= parsed
