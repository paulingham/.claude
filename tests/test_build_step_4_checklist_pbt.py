"""AC4.5 — Step 4 self-review checklist gains a PBT item.

Asserts the Step 4 self-review checklist contains a bullet referencing
Step 1d / `CLAUDE_PBT=0`.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = REPO_ROOT / "skills" / "build-implementation" / "SKILL.md"


def _step_4_body(body):
    """Return text from `### Step 4` heading up to the next `### ` heading."""
    lines = body.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith("### Step 4"):
            start = i
            break
    assert start is not None, "Step 4 heading not found"
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("### "):
            end = j
            break
    return "\n".join(lines[start:end])


def test_self_review_checklist_includes_pbt_item():
    body = SKILL_PATH.read_text()
    step_body = _step_4_body(body)
    # The new bullet must reference Step 1d AND the env hatch.
    assert "Step 1d" in step_body, (
        "Step 4 self-review checklist must reference Step 1d")
    assert "CLAUDE_PBT=0" in step_body, (
        "Step 4 self-review checklist must reference CLAUDE_PBT=0 hatch")
