"""Self-test for the Slice E.5 pipeline-state fixture helper."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _fixtures.pipeline_state import make_pipeline_fixture


def _content(path):
    return path.read_text() if path.exists() else None


def test_legacy_layout_writes_flat_pipeline_md(tmp_path):
    p = make_pipeline_fixture(tmp_path, "abc", layout="legacy")
    assert p == tmp_path / "abc-pipeline.md"
    assert p.exists()
    assert "task_id: abc" in p.read_text()


def test_new_layout_writes_subdir_pipeline_md(tmp_path):
    p = make_pipeline_fixture(tmp_path, "abc", layout="new")
    assert p == tmp_path / "abc" / "pipeline.md"
    assert p.exists()
    assert "task_id: abc" in p.read_text()


def test_legacy_layout_with_workstream(tmp_path):
    p = make_pipeline_fixture(tmp_path, "t1", layout="legacy", workstream="ws1")
    assert p == tmp_path / "workstreams" / "ws1" / "t1-pipeline.md"
    assert p.exists()


def test_new_layout_with_workstream(tmp_path):
    p = make_pipeline_fixture(tmp_path, "t1", layout="new", workstream="ws1")
    assert p == tmp_path / "workstreams" / "ws1" / "t1" / "pipeline.md"
    assert p.exists()


def test_phases_creates_each_named_phase_legacy(tmp_path):
    p = make_pipeline_fixture(
        tmp_path, "t1", layout="legacy", phases=["pipeline", "build", "review"])
    assert p == tmp_path / "t1-pipeline.md"
    assert (tmp_path / "t1-build.md").exists()
    assert (tmp_path / "t1-review.md").exists()


def test_phases_creates_each_named_phase_new(tmp_path):
    p = make_pipeline_fixture(
        tmp_path, "t1", layout="new", phases=["pipeline", "build"])
    assert p == tmp_path / "t1" / "pipeline.md"
    assert (tmp_path / "t1" / "build.md").exists()


def test_default_phase_is_pipeline_only(tmp_path):
    make_pipeline_fixture(tmp_path, "abc", layout="legacy")
    assert (tmp_path / "abc-pipeline.md").exists()
    assert not (tmp_path / "abc-build.md").exists()


def test_verdict_recorded_in_frontmatter(tmp_path):
    p = make_pipeline_fixture(
        tmp_path, "t1", layout="new", verdict="completed")
    assert "verdict: completed" in p.read_text()


def test_default_verdict_is_in_progress(tmp_path):
    p = make_pipeline_fixture(tmp_path, "t1", layout="new")
    assert "verdict: in_progress" in p.read_text()


def test_phase_field_is_per_phase(tmp_path):
    make_pipeline_fixture(
        tmp_path, "t1", layout="new", phases=["pipeline", "build"])
    assert "phase: pipeline" in (tmp_path / "t1" / "pipeline.md").read_text()
    assert "phase: build" in (tmp_path / "t1" / "build.md").read_text()


def test_invalid_layout_raises_valueerror(tmp_path):
    with pytest.raises(ValueError, match="layout must be"):
        make_pipeline_fixture(tmp_path, "t", layout="bogus")


def test_workstream_empty_string_means_root(tmp_path):
    p = make_pipeline_fixture(tmp_path, "t1", layout="new", workstream="")
    assert p == tmp_path / "t1" / "pipeline.md"


def test_workstream_none_means_root(tmp_path):
    p = make_pipeline_fixture(tmp_path, "t1", layout="new", workstream=None)
    assert p == tmp_path / "t1" / "pipeline.md"


def test_idempotent_overwrite(tmp_path):
    p1 = make_pipeline_fixture(tmp_path, "t1", layout="new")
    make_pipeline_fixture(tmp_path, "t1", layout="new", verdict="completed")
    assert "verdict: completed" in p1.read_text()


def test_returns_pipeline_md_path_when_phase_omitted_from_phases(tmp_path):
    """If phases=['build'], the helper still echoes a pipeline.md path."""
    p = make_pipeline_fixture(
        tmp_path, "t1", layout="new", phases=["build"])
    # build.md was written; pipeline.md was NOT — but path is still returned
    assert p == tmp_path / "t1" / "pipeline.md"
    assert not p.exists()
    assert (tmp_path / "t1" / "build.md").exists()
