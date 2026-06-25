"""AC1 (re-scoped, STRUCTURAL) — DEBT in comment-smell-check.sh exemption alternation.

This test is deliberately STRUCTURAL, not behavioral. An empirical finding during
build proved the `|DEBT` exemption is behaviorally INERT under the hook's current
verb-narration check: that check strips only the comment marker (`#`/`//`/`/*`) and
anchors `^(verb)` on the FIRST remaining word — which, for any prefixed comment, is
the prefix keyword itself (`DEBT:`), never the narration verb that follows. So:

  - `# DEBT: set inline cache` exits 0 with OR without `|DEBT` (no behavioral flip).
  - `# WHY: increment ...` exits 0 even with the ENTIRE line-111 exemption removed.

A behavioral RED-on-revert / exit-code test for the marker would therefore be vacuous
(passes either way) or assert a false fail-closed claim (bare `# DEBT` does not block
via the verb check — `DEBT` is not a verb). The exemption is forward-compat scaffolding:
it only becomes load-bearing if the verb-check is later changed to strip known prefixes.

This test guards the two things that ARE true and load-bearing about the edit:
  (a) `DEBT` literally appears inside the line-111 exemption alternation group;
  (b) the `:` stays OUTSIDE that group (regex ends `...|DEBT):`), so a bare `# DEBT`
      with no colon is NOT specially exempted (colon-strictness preserved).
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "hooks" / "comment-smell-check.sh"


def _exemption_line():
    """Return the single grep line that holds the prefix-exemption alternation."""
    for line in HOOK.read_text().splitlines():
        if "POSTCONDITION" in line and "grep" in line:
            return line
    return ""


class AC1DebtInExemptionAlternation(unittest.TestCase):
    def test_hook_exists(self):
        self.assertTrue(HOOK.exists(), f"hook must exist at {HOOK}")

    def test_debt_in_alternation_group(self):
        line = _exemption_line()
        self.assertTrue(line, "could not locate the prefix-exemption grep line")
        match = re.search(r"\(([^)]*\bDEBT\b[^)]*)\)", line)
        self.assertIsNotNone(
            match,
            "DEBT must appear inside the exemption alternation group on line 111")
        self.assertIn(
            "DEBT", match.group(1),
            "DEBT must be one of the alternation prefixes")

    def test_colon_is_outside_the_group(self):
        line = _exemption_line()
        self.assertRegex(
            line, r"\|DEBT\):",
            "the alternation must end `...|DEBT):` with the `:` OUTSIDE the group "
            "so bare `# DEBT` (no colon) is not specially exempted")

    def test_why_breadcrumb_present(self):
        text = HOOK.read_text()
        self.assertIn(
            "forward-compat", text.lower(),
            "a # WHY: breadcrumb must explain DEBT: is forward-compat scaffolding")
        self.assertIn(
            "/harness:debt-ledger", text,
            "the breadcrumb must point to the /harness:debt-ledger harvester")


if __name__ == "__main__":
    unittest.main()
