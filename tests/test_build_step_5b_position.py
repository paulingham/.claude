"""AC1 — Step 5b sits between Step 5 and the `## Verdict` heading.

Reads `skills/build-implementation/SKILL.md` and asserts the line index of
the `### Step 5b` (or `## Step 5b` — accept either heading level) heading
satisfies `idx_step_5 < idx_step_5b < idx_verdict_heading`. Position-only
check; AC1's body content is asserted by `test_build_step_5b_body.py`.
"""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = (
    REPO_ROOT / "skills" / "build-implementation" / "SKILL.md"
)


def _line_index_of_heading_prefix(lines, prefix_tokens):
    """Return the 0-based index of the first line that starts with any of
    the given heading prefixes. Returns -1 if no match.

    `prefix_tokens` is an iterable of strings; each is matched against the
    line *stripped of trailing whitespace*, accepting any leading `#` count
    so callers don't have to disambiguate `### Step 5b` vs `## Step 5b`.
    """
    for idx, line in enumerate(lines):
        stripped = line.rstrip()
        for token in prefix_tokens:
            if stripped == token or stripped.startswith(token + " "):
                return idx
    return -1


class Step5bSitsBetweenStep5AndVerdict(unittest.TestCase):
    """AC1 position contract."""

    def setUp(self):
        self.lines = SKILL_PATH.read_text().splitlines()

    def test_ac1_step_5b_sits_between_step_5_and_verdict(self):
        # Step 5 heading — current SKILL.md uses `## Step 5: ...`.
        idx_step_5 = _line_index_of_heading_prefix(
            self.lines,
            ["## Step 5:"]
        )
        self.assertGreater(
            idx_step_5, -1,
            "Step 5 heading must exist in build-implementation SKILL.md")

        # Step 5b heading — accept `### Step 5b` (sub-heading of Step 5)
        # OR `## Step 5b` (peer heading). Either matches the plan's intent.
        idx_step_5b = _line_index_of_heading_prefix(
            self.lines,
            ["### Step 5b:", "## Step 5b:"]
        )
        self.assertGreater(
            idx_step_5b, idx_step_5,
            "Step 5b heading must appear AFTER Step 5 heading")

        # Verdict heading — current file uses `## Verdict`.
        idx_verdict = _line_index_of_heading_prefix(
            self.lines,
            ["## Verdict"]
        )
        self.assertGreater(
            idx_verdict, idx_step_5b,
            "`## Verdict` heading must appear AFTER Step 5b heading")


if __name__ == "__main__":
    unittest.main()
