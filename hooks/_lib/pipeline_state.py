"""Active pipeline state file discovery. Picks newest *-pipeline.md by mtime."""
import glob
import os
from pathlib import Path

from pipeline_frontmatter import coerce_state, parse_frontmatter


def _state_dir(state_dir):
    return state_dir or os.environ.get("CLAUDE_PIPELINE_STATE_DIR") \
        or str(Path.home() / ".claude" / "pipeline-state")


def _find_pipeline_file(directory):
    files = glob.glob(str(Path(directory) / "*-pipeline.md"))
    files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return files[0] if files else None


def _debug_file_exists(directory, task_id):
    return bool(task_id) and Path(directory, f"{task_id}-debug.md").exists()


def read_active_state(state_dir=None):
    directory = _state_dir(state_dir)
    pipeline_file = _find_pipeline_file(directory)
    fields = parse_frontmatter(Path(pipeline_file).read_text()) if pipeline_file else {}
    return coerce_state(fields, _debug_file_exists(directory, fields.get("task_id", "")))
