"""AC4.1 — `### Step 1d` heading sits between Step 1c and Step 2.

Asserts the line index of `### Step 1d` is greater than `### Step 1c`
and less than `### Step 2:` in `skills/build-implementation/SKILL.md`.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = REPO_ROOT / "skills" / "build-implementation" / "SKILL.md"


def _heading_index(body, heading_prefix):
    """Return zero-based line index of the first line starting with the prefix."""
    for index, line in enumerate(body.splitlines()):
        if line.startswith(heading_prefix):
            return index
    return None


def test_step_1d_sits_between_1c_and_2():
    body = SKILL_PATH.read_text()
    idx_1c = _heading_index(body, "### Step 1c")
    idx_1d = _heading_index(body, "### Step 1d")
    idx_2 = _heading_index(body, "### Step 2:")
    assert idx_1c is not None, "missing `### Step 1c` heading"
    assert idx_1d is not None, "missing `### Step 1d` heading"
    assert idx_2 is not None, "missing `### Step 2:` heading"
    assert idx_1c < idx_1d < idx_2, (
        f"Step 1d must sit between Step 1c and Step 2 — got "
        f"1c={idx_1c}, 1d={idx_1d}, 2={idx_2}")
