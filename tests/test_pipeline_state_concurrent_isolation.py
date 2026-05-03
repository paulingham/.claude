"""Slice E (AC #8) — concurrent isolation across per-task subdirs.

Two pipelines (`t1` and `t2`) materialise as sibling per-task subdirs.
Each is independently discoverable; cleanup of one leaves the other
intact; parallel writers to disjoint subdirs do not contend.

These are integration-style tests against the DUAL_PATH composition:
they exercise `find_pipeline_files` (Slice A) over fixtures produced by
`_fixtures.pipeline_state.make_pipeline_fixture` (Slice E.5).
"""
import shutil
import threading
from pathlib import Path

from _fixtures.pipeline_state import make_pipeline_fixture
from pipeline_state_paths import find_pipeline_files


def _both_pipelines(state_dir: Path) -> tuple[Path, Path]:
    p1 = make_pipeline_fixture(state_dir, "t1", layout="new")
    p2 = make_pipeline_fixture(state_dir, "t2", layout="new")
    return p1, p2


def test_two_pipelines_no_state_collision(tmp_path):
    p1, p2 = _both_pipelines(tmp_path)
    found = set(find_pipeline_files(tmp_path))
    assert {p1, p2} <= found
    shutil.rmtree(tmp_path / "t1")
    assert not p1.exists()
    assert p2.exists()
    assert find_pipeline_files(tmp_path) == [p2]


def _writer(state_dir: Path, task_id: str) -> None:
    make_pipeline_fixture(state_dir, task_id, layout="new")


def _spawn_writers(state_dir: Path, count: int) -> None:
    threads = [
        threading.Thread(target=_writer, args=(state_dir, f"task-{i}"))
        for i in range(count)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


def test_concurrent_writes_isolate_per_task(tmp_path):
    _spawn_writers(tmp_path, 8)
    found = {p.parent.name for p in find_pipeline_files(tmp_path)}
    assert found == {f"task-{i}" for i in range(8)}
    for i in range(8):
        path = tmp_path / f"task-{i}" / "pipeline.md"
        assert path.exists(), f"task-{i}/pipeline.md missing"
        assert "task_id: task-" in path.read_text()
