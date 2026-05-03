"""Slice A — bash-bridge CLI for pipeline_state_paths helpers.

Sourceable bash helpers (`_psp_find_active_pipelines`, `_psp_discover_state_path`)
delegate to this script — Python owns the mtime+precedence logic, bash owns
the user-facing CLI surface. Reads CLAUDE_PIPELINE_STATE_DIR or PSP_DIR for
the state directory.
"""
import os
import sys
from pathlib import Path

from pipeline_state_paths import discover_state_path, find_pipeline_files


def _state_dir() -> Path:
    raw = os.environ.get("CLAUDE_PIPELINE_STATE_DIR") or os.environ.get("PSP_DIR")
    return Path(raw) if raw else Path.home() / ".claude" / "pipeline-state"


def _cmd_find():
    for path in find_pipeline_files(_state_dir()):
        print(str(path))


def _cmd_discover(task: str, phase: str, workstream: str):
    ws = workstream or None
    found = discover_state_path(_state_dir(), task, phase, ws)
    if found is not None:
        print(str(found))


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "find":
        _cmd_find()
    elif cmd == "discover":
        _cmd_discover(argv[2], argv[3], argv[4] if len(argv) > 4 else "")


if __name__ == "__main__":
    main(sys.argv)
