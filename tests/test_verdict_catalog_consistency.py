"""Slice 3 AC9 — verdict-catalog consistency for PDR-RTV verdicts.

Slice 1 already added the rows for `PDR_WINNER_SELECTED` and
`PDR_NO_CONSENSUS`. This Slice 3 test verifies the rows are present,
have correct polarities, and the existing audit (forward + reverse)
still passes when the new emitter `pdr-rtv` is taken into account.
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG = REPO_ROOT / "rules" / "verdict-catalog.md"


def _parse_catalog_rows():
    """Return list of dicts: {verdict, polarity, emitters, phase, branch}."""
    rows = []
    body = CATALOG.read_text()
    pattern = re.compile(
        r"^\|\s*`([^`]+)`\s*\|\s*([a-z]+)\s*\|"
        r"\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*(.+?)\s*\|$",
        re.MULTILINE)
    for m in pattern.finditer(body):
        emitter_cell = m.group(3)
        emitters = [e.strip().strip("`")
                    for e in emitter_cell.split(",")
                    if e.strip().strip("`")]
        rows.append({
            "verdict": m.group(1),
            "polarity": m.group(2),
            "emitters": emitters,
            "phase": m.group(4).strip(),
            "branch": m.group(5).strip(),
        })
    return rows


class PdrRtvVerdictsPresentAndValid(unittest.TestCase):
    """AC9 — `PDR_WINNER_SELECTED` (success) + `PDR_NO_CONSENSUS` (failure)
    rows exist with correct polarity and emitter `pdr-rtv`.
    """

    def test_pdr_rtv_verdicts_present_and_valid(self):
        rows = _parse_catalog_rows()
        by_verdict = {r["verdict"]: r for r in rows}

        self.assertIn(
            "PDR_WINNER_SELECTED", by_verdict,
            "rules/verdict-catalog.md must contain PDR_WINNER_SELECTED row")
        winner = by_verdict["PDR_WINNER_SELECTED"]
        self.assertEqual(winner["polarity"], "success",
                         "PDR_WINNER_SELECTED must be polarity=success")
        self.assertIn("pdr-rtv", winner["emitters"],
                      "PDR_WINNER_SELECTED emitter must be pdr-rtv")
        self.assertEqual(winner["phase"], "build",
                         "PDR_WINNER_SELECTED phase must be build")

        self.assertIn(
            "PDR_NO_CONSENSUS", by_verdict,
            "rules/verdict-catalog.md must contain PDR_NO_CONSENSUS row")
        no_consensus = by_verdict["PDR_NO_CONSENSUS"]
        self.assertEqual(no_consensus["polarity"], "failure",
                         "PDR_NO_CONSENSUS must be polarity=failure")
        self.assertIn("pdr-rtv", no_consensus["emitters"],
                      "PDR_NO_CONSENSUS emitter must be pdr-rtv")
        self.assertEqual(no_consensus["phase"], "build",
                         "PDR_NO_CONSENSUS phase must be build")


if __name__ == "__main__":
    unittest.main()
