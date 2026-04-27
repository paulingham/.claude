"""Deterministic new-finding pre-filter for the continuous planning agent.

Returns only scratchpad findings not yet recorded in the cursor (tracked by
content hash). Does NOT classify findings — that is the planning agent's job.
"""
import json
from pathlib import Path
from typing import Union

from scratchpad_finding_parser import Finding, content_hash, parse_finding

PathLike = Union[Path, str]


def diff_new_findings(scratchpad_dir: PathLike, cursor_path: PathLike) -> list[Finding]:
    """Return findings in scratchpad_dir not yet recorded in cursor_path."""
    scratch = Path(scratchpad_dir)
    cursor = Path(cursor_path)
    if not scratch.is_dir():
        return []
    seen = _load_cursor(cursor)
    new = _collect_new(scratch, seen)
    _save_cursor(cursor, seen | {(f["filename"], f["content_hash"]) for f in new})
    return new


def _collect_new(scratch: Path, seen: set[tuple[str, str]]) -> list[Finding]:
    return [f for f in (parse_finding(p) for p in sorted(scratch.glob("*.md")))
            if f is not None and (f["filename"], f["content_hash"]) not in seen]


def _load_cursor(cursor_path: Path) -> set[tuple[str, str]]:
    if not cursor_path.is_file():
        return set()
    try:
        raw = json.loads(cursor_path.read_text())
        return {(item["filename"], item["content_hash"]) for item in raw}
    except (json.JSONDecodeError, KeyError, TypeError):
        return set()


def _save_cursor(cursor_path: Path, seen: set[tuple[str, str]]) -> None:
    payload = [{"filename": fn, "content_hash": h} for fn, h in sorted(seen)]
    cursor_path.parent.mkdir(parents=True, exist_ok=True)
    cursor_path.write_text(json.dumps(payload, indent=2))


# Re-export for tests that already import these via scratchpad_diff
_content_hash = content_hash
_parse_finding = parse_finding
