"""Slice C — text-grep tests asserting state-writing skills document the new layout.

These tests verify that the SKILL.md files for state-writing skills point
write paths at `pipeline-state/{task-id}/{phase}.md` (per-task subdir),
NOT the legacy flat `{task-id}-{phase}.md` form. Doc-grep, not invocation —
the runtime behaviour change is "the next pipeline that invokes this skill
writes to the new layout".
"""
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS = REPO_ROOT / "skills"


def _read(skill_name: str) -> str:
    return (SKILLS / skill_name / "SKILL.md").read_text()


def test_pipeline_skill_creates_state_under_subdir():
    """`/pipeline` Step 2c documents pipeline-state/{task-id}/pipeline.md."""
    text = _read("pipeline")
    assert "pipeline-state/{task-id}/pipeline.md" in text
    assert "pipeline-state/[feature-name]/pipeline.md" in text


def test_intake_writes_intake_md_under_subdir():
    """intake Step 2d documents new-layout intake.md write path."""
    text = _read("intake")
    assert "pipeline-state/{task-id}/intake.md" in text
    assert "pipeline-state/{task-id}/discussion.md" in text


def test_greenfield_writes_product_brief_under_subdir():
    """greenfield-scaffold Step 1 documents new-layout product-brief.md."""
    text = _read("greenfield-scaffold")
    assert "pipeline-state/{task-id}/product-brief.md" in text
    assert "pipeline-state/{task-id}/tech-stack.md" in text
    assert "pipeline-state/{task-id}/ui-architecture.md" in text


def test_module_extraction_writes_boundary_analysis_under_subdir():
    """module-extraction documents new-layout boundary-analysis.md."""
    text = _read("module-extraction")
    assert "pipeline-state/{task-id}/boundary-analysis.md" in text


def test_continuous_planning_writes_planning_cursor_under_subdir():
    """continuous-planning documents new-layout planning-cursor.json."""
    text = _read("continuous-planning")
    assert "pipeline-state/{task-id}/planning-cursor.json" in text
    assert "pipeline-state/{task-id}/plan.md" in text
    assert "pipeline-state/{task-id}/scratchpad/" in text
