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
