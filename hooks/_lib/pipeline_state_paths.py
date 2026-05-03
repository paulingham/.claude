"""Slice A — DUAL_PATH pipeline-state path public API.

NEW layout: `pipeline-state/{task-id}/{phase}.md` (workstream variant
prefixes `workstreams/{ws}/`). LEGACY: `pipeline-state/{task-id}-{phase}.md`.
Discovery tolerates both during the 90-day soak; workstream beats root
on collision; fresher mtime wins; ties favour new layout.
"""
from pathlib import Path
from typing import Optional

from pipeline_state_paths_helpers import (
    legacy_paths, new_paths, task_id_of, ws_root,
)
from pipeline_state_paths_precedence import better, pick_existing


def task_state_path(state_dir: Path, task_id: str, phase: str,
                    workstream: Optional[str] = None) -> Path:
    """NEW-LAYOUT write path. workstream=None and workstream='' both mean root."""
    return ws_root(state_dir, workstream) / task_id / f"{phase}.md"


def find_pipeline_files(state_dir: Path) -> list:
    """All pipeline.md files under both layouts, deduped by task_id (workstream beats root)."""
    state_dir = Path(state_dir)
    winners = {}
    for path in new_paths(state_dir) + legacy_paths(state_dir):
        tid = task_id_of(path)
        winners[tid] = better(winners.get(tid), path, state_dir)
    return list(winners.values())


def discover_state_path(state_dir: Path, task_id: str, phase: str,
                        workstream: Optional[str] = None) -> Optional[Path]:
    """Whichever layout has fresher mtime; ties favour new. None if neither exists."""
    new = task_state_path(state_dir, task_id, phase, workstream)
    legacy = ws_root(state_dir, workstream) / f"{task_id}-{phase}.md"
    return pick_existing(new, legacy)
