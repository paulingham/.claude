"""Slice A — precedence rules for pipeline_state_paths."""
from pathlib import Path
from typing import Optional

from pipeline_state_paths_helpers import is_workstream


def better(current, candidate, state_dir):
    """Workstream beats root; else fresher mtime; else new (basename pipeline.md) beats legacy."""
    if current is None:
        return candidate
    cur_ws, can_ws = is_workstream(current, state_dir), is_workstream(candidate, state_dir)
    if cur_ws != can_ws:
        return candidate if can_ws else current
    cur_m, can_m = current.stat().st_mtime, candidate.stat().st_mtime
    if can_m != cur_m:
        return candidate if can_m > cur_m else current
    return candidate if candidate.name == "pipeline.md" else current


def pick_existing(new: Path, legacy: Path) -> Optional[Path]:
    if not new.exists() and not legacy.exists():
        return None
    if not legacy.exists():
        return new
    if not new.exists():
        return legacy
    return new if new.stat().st_mtime >= legacy.stat().st_mtime else legacy
