"""Active pipeline state file discovery + frontmatter parsing. Pure I/O."""
import glob
import os
import re
from pathlib import Path

_TRUE = {"true", "yes", "1"}


def _state_dir(state_dir):
    return state_dir or os.environ.get("CLAUDE_PIPELINE_STATE_DIR") \
        or str(Path.home() / ".claude" / "pipeline-state")


def _find_pipeline_file(directory):
    files = sorted(glob.glob(str(Path(directory) / "*-pipeline.md")))
    return files[0] if files else None


def _parse_frontmatter(text):
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    return dict(_kv(line) for line in match.group(1).splitlines() if ":" in line) if match else {}


def _kv(line):
    key, _, value = line.partition(":")
    return key.strip(), value.strip()


def _coerce(fields):
    return {
        "task_id": fields.get("task_id", ""),
        "phase": fields.get("phase", ""),
        "critical": fields.get("critical", "").lower() in _TRUE,
        "budget": int(fields.get("budget", "0") or 0),
        "debug_active": fields.get("phase", "") == "debugging",
    }


def read_active_state(state_dir=None):
    directory = _state_dir(state_dir)
    pipeline_file = _find_pipeline_file(directory)
    if not pipeline_file:
        return _coerce({})
    return _coerce(_parse_frontmatter(Path(pipeline_file).read_text()))
