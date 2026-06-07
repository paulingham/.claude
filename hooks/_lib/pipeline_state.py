"""Active pipeline state file discovery — DUAL_PATH (new + legacy layouts)."""
import os
from pathlib import Path

from harness_paths import harness_data
from pipeline_frontmatter import coerce_state, parse_frontmatter
from pipeline_state_paths import discover_state_path, find_pipeline_files


def _state_dir(state_dir):
    # CLAUDE_PIPELINE_STATE_DIR is tier 1 by design (M-d); harness_data() is cold-start fallback.
    return state_dir or os.environ.get("CLAUDE_PIPELINE_STATE_DIR") \
        or str(harness_data() / "pipeline-state")


def _find_pipeline_file(directory):
    files = find_pipeline_files(Path(directory))
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return str(files[0]) if files else None


def active_pipeline_path(state_dir=None):
    """Return Path to the mtime-newest pipeline file, or None if none found.

    Single source of truth for active-pipeline resolution used by both
    read_active_state and any caller that needs the same selection.
    """
    directory = _state_dir(state_dir)
    result = _find_pipeline_file(directory)
    return Path(result) if result else None


def _debug_path(directory, task_id):
    return discover_state_path(Path(directory), task_id, "debug") if task_id else None


def _debug_mtime(path):
    return os.path.getmtime(path) if path and path.exists() else None


def read_active_state(state_dir=None):
    directory = _state_dir(state_dir)
    pipeline_file = _find_pipeline_file(directory)
    fields = parse_frontmatter(Path(pipeline_file).read_text()) if pipeline_file else {}
    mtime = _debug_mtime(_debug_path(directory, fields.get("task_id", "")))
    return coerce_state(fields, mtime is not None, mtime)
