"""AC4.2 — Step 1d body invokes /property-based-test, names verdicts and reason codes.

Asserts Step 1d body references the skill, names all three verdicts,
names the PBT_SKIPPED reason codes, and names the halt-on-PBT_BLOCKED
rule.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = REPO_ROOT / "skills" / "build-implementation" / "SKILL.md"

VERDICTS = ("PBT_AUTHORED", "PBT_SKIPPED", "PBT_BLOCKED")
SKIPPED_REASONS = ("env-hatch", "no-candidates", "no-framework-for-language")


def _step_1d_body(body):
    """Return text from `### Step 1d` heading up to the next `### Step ` heading."""
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


def test_step_1d_invokes_pbt_skill_with_verdicts_and_reason_codes():
    body = SKILL_PATH.read_text()
    step_body = _step_1d_body(body)
    assert "/property-based-test" in step_body, (
        "Step 1d body must reference the /property-based-test skill")
    missing_verdicts = [v for v in VERDICTS if v not in step_body]
    assert not missing_verdicts, (
        f"Step 1d body missing verdicts: {missing_verdicts!r}")
    missing_reasons = [r for r in SKIPPED_REASONS if r not in step_body]
    assert not missing_reasons, (
        f"Step 1d body missing PBT_SKIPPED reason codes: "
        f"{missing_reasons!r}")
    assert "halt" in step_body.lower(), (
        "Step 1d body must name the halt-on-PBT_BLOCKED rule")
