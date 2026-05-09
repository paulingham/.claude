"""AC4.3 — Step 1d body documents CLAUDE_PBT=0 in canonical style.

Asserts Step 1d body contains `**Escape hatch.**` heading and
`CLAUDE_PBT=0` substring; structural match to the
`build-implementation:77` style block.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = REPO_ROOT / "skills" / "build-implementation" / "SKILL.md"


def _step_1d_body(body):
    lines = body.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith("### Step 1d"):
            start = i
            break
    assert start is not None, "Step 1d heading not found"
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("### Step "):
            end = j
            break
    return "\n".join(lines[start:end])


def test_step_1d_documents_pbt_env_hatch_in_canonical_style():
    body = SKILL_PATH.read_text()
    step_body = _step_1d_body(body)
    assert "**Escape hatch.**" in step_body, (
        "Step 1d body missing `**Escape hatch.**` heading "
        "(canonical style mirroring build-implementation:77)")
    assert "CLAUDE_PBT=0" in step_body, (
        "Step 1d body must reference CLAUDE_PBT=0 env hatch")
