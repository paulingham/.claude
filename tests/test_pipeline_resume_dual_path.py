"""Slice D — pipeline-resume dual-path discovery contract tests (AC #2).

Locks the resume scan logic against:

1. New-layout root pipelines (`pipeline-state/{task}/pipeline.md`)
2. New-layout workstream-nested pipelines
   (`pipeline-state/workstreams/{ws}/{task}/pipeline.md`)
3. The literal glob pattern documented in `skills/pipeline-resume/SKILL.md`
4. Health-reports exclusion — `pipeline-state/health-reports/<date>.md` is
   NOT a task pipeline and must never be returned by an active-pipeline scan.

Implementation contract: the SKILL.md text MUST document the four-glob
discovery sequence (new-root, new-workstream, legacy-root, legacy-workstream)
and call out the dedup rule (workstream-wins, mtime tiebreak). The actual
runtime helper is `pipeline_state_paths.find_pipeline_files` (Slice A);
these tests pin its behaviour for Slice D's specific scenarios so future
SKILL.md edits cannot drift away from the helper contract.
"""
import glob
from pathlib import Path

from pipeline_state_paths import find_pipeline_files
from _fixtures.pipeline_state import make_pipeline_fixture

REPO_ROOT = Path(__file__).resolve().parent.parent
RESUME_SKILL = REPO_ROOT / "skills" / "pipeline-resume" / "SKILL.md"
WORKSTREAM_SKILL = REPO_ROOT / "skills" / "workstream" / "SKILL.md"


def test_resume_finds_new_layout_pipeline(tmp_path):
    """Helper returns new-layout fixture AND SKILL.md documents new layout."""
    fixture = make_pipeline_fixture(tmp_path, "t1", layout="new")
    assert fixture in find_pipeline_files(tmp_path)
    assert "pipeline-state/{task-id}/pipeline.md" in RESUME_SKILL.read_text()


def test_resume_finds_workstream_nested_pipeline(tmp_path):
    """Helper returns workstream fixture AND workstream SKILL.md documents new layout."""
    fixture = make_pipeline_fixture(
        tmp_path, "t1", layout="new", workstream="auth")
    assert fixture in find_pipeline_files(tmp_path)
    text = WORKSTREAM_SKILL.read_text()
    assert "pipeline-state/workstreams/{name}/{task-id}/pipeline.md" in text


def test_resume_glob_pattern_matches_pipeline_md(tmp_path):
    """SKILL.md documents `*/pipeline.md` glob; pattern resolves new fixture."""
    fixture = make_pipeline_fixture(tmp_path, "t1", layout="new")
    skill_text = RESUME_SKILL.read_text()
    pattern = f"{tmp_path}/*/pipeline.md"
    assert "*/pipeline.md" in skill_text
    assert str(fixture) in glob.glob(pattern)


def test_resume_excludes_health_reports_dir(tmp_path):
    """`pipeline-state/health-reports/2026-04-30.md` is NOT a task pipeline."""
    health_dir = tmp_path / "health-reports"
    health_dir.mkdir()
    (health_dir / "2026-04-30.md").write_text("---\n---\n")
    assert find_pipeline_files(tmp_path) == []
