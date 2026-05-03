"""Slice E (AC #8) — workstream-nested pipeline composition.

A workstream-nested pipeline at `pipeline-state/workstreams/{ws}/{task}/pipeline.md`
must be:
  1. Discovered by `find_pipeline_files`
  2. Cleanable via `rm -rf` of just the task subdir (workstream dir intact)
  3. Coexist with a root-level pipeline that has a different task_id
  4. Win precedence over a root-level pipeline that shares the same task_id
     (precedence rule from Slice A — already covered by
     `test_dual_path_discovery::test_workstream_beats_root_on_task_id_collision`;
     this slice asserts the coexist-when-distinct case)
"""
import shutil
from pathlib import Path

from _fixtures.pipeline_state import make_pipeline_fixture
from pipeline_state_paths import find_pipeline_files


def test_workstream_nested_compose_correctly(tmp_path):
    nested = make_pipeline_fixture(
        tmp_path, "t1", layout="new", workstream="ws1"
    )
    expected = tmp_path / "workstreams" / "ws1" / "t1" / "pipeline.md"
    assert nested == expected
    assert nested in find_pipeline_files(tmp_path)
    shutil.rmtree(tmp_path / "workstreams" / "ws1" / "t1")
    assert not nested.exists()
    assert (tmp_path / "workstreams" / "ws1").exists(), \
        "workstream dir must survive task-subdir cleanup"


def test_workstream_and_root_pipelines_coexist(tmp_path):
    root = make_pipeline_fixture(tmp_path, "root-task", layout="new")
    nested = make_pipeline_fixture(
        tmp_path, "ws-task", layout="new", workstream="ws1"
    )
    found = set(find_pipeline_files(tmp_path))
    assert {root, nested} <= found
