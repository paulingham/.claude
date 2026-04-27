"""Cursor persistence for the scratchpad-diff pre-filter.

Tracks which (filename, content_hash) tuples have already been surfaced to the
planning agent. Stored as a sorted JSON array on disk so cursor files diff
cleanly across runs.
"""
import json
from pathlib import Path


def load_cursor(cursor_path: Path) -> set[tuple[str, str]]:
    """Return the set of (filename, content_hash) tuples seen so far."""
    if not cursor_path.is_file():
        return set()
    try:
        raw = json.loads(cursor_path.read_text())
        return {(item["filename"], item["content_hash"]) for item in raw}
    except (json.JSONDecodeError, KeyError, TypeError):
        return set()


def save_cursor(cursor_path: Path, seen: set[tuple[str, str]]) -> None:
    """Persist the seen set as a sorted JSON array."""
    payload = [{"filename": fn, "content_hash": h} for fn, h in sorted(seen)]
    cursor_path.parent.mkdir(parents=True, exist_ok=True)
    cursor_path.write_text(json.dumps(payload, indent=2))
