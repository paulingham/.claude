"""AC2 — engineering-invariants.md § Comments documents the DEBT: marker convention.

The convention is `DEBT: <ceiling>, <upgrade-trigger>`:
  - ceiling        = the accepted complexity / simplification limit;
  - upgrade-trigger = the condition that should prompt revisiting.
An entry with no upgrade-trigger (no second clause after the comma) is silent rot.
The marker is harvested by /harness:debt-ledger.
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INVARIANTS = REPO_ROOT / "protocols" / "engineering-invariants.md"


def _comments_section():
    text = INVARIANTS.read_text()
    match = re.search(
        r"##\s*Comments\s*\n(.+?)(?=\n##\s|\Z)", text, re.DOTALL)
    return match.group(1) if match else ""


class AC2DebtConventionDocumented(unittest.TestCase):
    def test_comments_section_exists(self):
        self.assertTrue(_comments_section(), "§ Comments section must exist")

    def test_debt_marker_named(self):
        self.assertIn(
            "DEBT:", _comments_section(),
            "§ Comments must name the DEBT: marker")

    def test_ceiling_and_upgrade_trigger_grammar(self):
        section = _comments_section().lower()
        self.assertIn(
            "ceiling", section,
            "§ Comments must define the <ceiling> half of the DEBT: grammar")
        self.assertIn(
            "upgrade-trigger", section,
            "§ Comments must define the <upgrade-trigger> half of the grammar")

    def test_no_trigger_is_silent_rot(self):
        section = _comments_section().lower()
        self.assertIn(
            "silent rot", section,
            "§ Comments must note that a DEBT: entry with no upgrade-trigger is silent rot")

    def test_harvested_by_debt_ledger(self):
        self.assertIn(
            "/harness:debt-ledger", _comments_section(),
            "§ Comments must note the marker is harvested by /harness:debt-ledger")


if __name__ == "__main__":
    unittest.main()
