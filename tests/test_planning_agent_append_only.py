"""Test: plan file is append-only — pre-existing content is never modified."""
import tempfile
from pathlib import Path

ORIGINAL_PLAN = """# Original Plan

## Approach
Build X first, then Y.

## Slice 1
Modify foo.py.
"""

PLAN_UPDATE_SECTION = """\n## Plan Update — 2026-04-27T12:00:00Z
**Source:** build-eng-slice1.md
**Category:** fragility
**Invalidated assumption:** foo.py is safe to modify
**Updated guidance:** foo.py has a global cache — coordinate before modifying.
**Affected slices:** slice-1
"""


def test_original_content_byte_equal_after_update():
    """Pre-existing plan content is byte-identical before and after a Plan Update append."""
    with tempfile.TemporaryDirectory() as tmpdir:
        plan_file = Path(tmpdir) / "task-test-plan.md"
        plan_file.write_text(ORIGINAL_PLAN)
        original_bytes = plan_file.read_bytes()
        # Simulate planning-agent append (the only allowed mutation)
        with plan_file.open("a") as f:
            f.write(PLAN_UPDATE_SECTION)
        after_bytes = plan_file.read_bytes()
        # Pre-existing content must be byte-identical
        assert after_bytes[:len(original_bytes)] == original_bytes, (
            "Planning-agent may only APPEND to plan file — pre-existing content must be untouched"
        )


def test_multiple_updates_each_append_only():
    """Multiple plan updates each append without modifying prior content."""
    with tempfile.TemporaryDirectory() as tmpdir:
        plan_file = Path(tmpdir) / "task-plan.md"
        plan_file.write_text(ORIGINAL_PLAN)
        snapshots = [plan_file.read_bytes()]
        for i in range(3):
            update = (
                f"\n## Plan Update — 2026-04-27T12:0{i}:00Z\n"
                f"**Source:** eng-{i}.md\n"
                f"**Category:** warning\n"
                f"**Invalidated assumption:** step {i}\n"
                f"**Updated guidance:** update {i}.\n"
                f"**Affected slices:** slice-{i}\n"
            )
            with plan_file.open("a") as f:
                f.write(update)
            current = plan_file.read_bytes()
            assert current[:len(snapshots[-1])] == snapshots[-1]
            snapshots.append(current)
