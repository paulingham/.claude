"""Deterministic new-finding pre-filter for the continuous planning agent.

Two-phase API: ``peek_new_findings`` returns unseen findings WITHOUT touching
the cursor; ``commit_findings`` marks them seen. Poll loop peeks, processes
(e.g. edits the plan file), then commits — if it crashes between, findings
are re-surfaced on the next poll. Correctness over efficiency.

``diff_new_findings`` is a peek+commit convenience for ad-hoc/legacy callers.
"""
from __future__ import annotations

from pathlib import Path
from typing import Union

from scratchpad_cursor import load_cursor, save_cursor
from scratchpad_finding_parser import Finding, content_hash, parse_finding

PathLike = Union[Path, str]


def peek_new_findings(scratchpad_dir: PathLike, cursor_path: PathLike) -> list[Finding]:
    """Return new findings WITHOUT updating the cursor."""
    scratch = Path(scratchpad_dir)
    if not scratch.is_dir():
        return []
    return _collect_new(scratch, load_cursor(Path(cursor_path)))


def commit_findings(findings: list[Finding], cursor_path: PathLike) -> None:
    """Mark the given findings as seen by extending the cursor."""
    if not findings:
        return
    cursor = Path(cursor_path)
    seen = load_cursor(cursor) | {(f["filename"], f["content_hash"]) for f in findings}
    save_cursor(cursor, seen)


def diff_new_findings(scratchpad_dir: PathLike, cursor_path: PathLike) -> list[Finding]:
    """Peek new findings and immediately commit them. Convenience wrapper."""
    new = peek_new_findings(scratchpad_dir, cursor_path)
    commit_findings(new, cursor_path)
    return new


def _collect_new(scratch: Path, seen: set[tuple[str, str]]) -> list[Finding]:
    return [f for f in (parse_finding(p) for p in sorted(scratch.glob("*.md")))
            if f is not None and (f["filename"], f["content_hash"]) not in seen]


# Legacy aliases for tests / callers that imported via scratchpad_diff.
_content_hash, _parse_finding = content_hash, parse_finding
_load_cursor, _save_cursor = load_cursor, save_cursor
