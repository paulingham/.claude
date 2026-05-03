"""Slice A — dual-path discovery + precedence contract tests."""
import os
from pathlib import Path

from pipeline_state_paths import find_pipeline_files


def _touch(path, mtime):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\nverdict: in_progress\n---\n")
    os.utime(path, (mtime, mtime))


def test_legacy_layout_still_discoverable(tmp_path):
    legacy = tmp_path / "t1-pipeline.md"
    _touch(legacy, 1000.0)
    assert legacy in find_pipeline_files(tmp_path)


def test_fresher_layout_wins_on_collision(tmp_path):
    legacy = tmp_path / "t1-pipeline.md"
    new = tmp_path / "t1" / "pipeline.md"
    _touch(legacy, 1000.0)
    _touch(new, 2000.0)
    assert find_pipeline_files(tmp_path) == [new]


def test_stale_new_layout_does_not_eclipse_live_legacy(tmp_path):
    new = tmp_path / "t1" / "pipeline.md"
    legacy = tmp_path / "t1-pipeline.md"
    _touch(new, 1000.0)
    _touch(legacy, 2000.0)
    assert find_pipeline_files(tmp_path) == [legacy]


def test_workstream_beats_root_on_task_id_collision(tmp_path):
    root = tmp_path / "t1" / "pipeline.md"
    workstream = tmp_path / "workstreams" / "ws1" / "t1" / "pipeline.md"
    _touch(root, 5000.0)
    _touch(workstream, 1000.0)
    assert find_pipeline_files(tmp_path) == [workstream]


def test_in_flight_pipeline_resumable(tmp_path):
    legacy = tmp_path / "in-flight-pipeline.md"
    _touch(legacy, 1000.0)
    assert legacy in find_pipeline_files(tmp_path)


# Slice B — approval-token read precedence (AC #6).
import os as _os
import subprocess as _sp
from pathlib import Path as _Path

_LIB = _Path(__file__).resolve().parents[1] / "hooks" / "_lib" / "approval-token.sh"


def _at_token_path(home: _Path, task_id: str) -> str:
    env = dict(_os.environ); env["HOME"] = str(home)
    result = _sp.run(
        ["bash", "-c", f"source '{_LIB}' && _at_token_path '{task_id}'"],
        capture_output=True, text=True, env=env, timeout=15,
    )
    return result.stdout.strip()


def test_approval_token_path_returns_existing_layout(tmp_path):
    home = tmp_path
    state = home / ".claude" / "pipeline-state"
    state.mkdir(parents=True)
    legacy = state / "tA-approval.token"
    legacy.write_text("{}")
    assert _at_token_path(home, "tA") == str(legacy)
    legacy.unlink()
    new_dir = state / "tA"; new_dir.mkdir()
    new = new_dir / "approval.token"
    new.write_text("{}")
    assert _at_token_path(home, "tA") == str(new)
