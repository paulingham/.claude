"""AC1 — verdict-catalog rows for the three SANDBOX verdicts.

Parses `rules/verdict-catalog.md` with the same regex
`tests/test_verdict_catalog_consistency.py` uses, asserts each of the
three new verdicts has the correct polarity, emitter (`sandbox-verify`),
phase (`build`), AND that the SANDBOX_SKIPPED branch column mentions the
`no-e2b-token` reason enum value (Story-1 scope).
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG = REPO_ROOT / "rules" / "verdict-catalog.md"


def _parse_catalog_rows():
    """Return list of dicts: {verdict, polarity, emitters, phase, branch}.

    Mirrors `tests/test_verdict_catalog_consistency.py:_parse_catalog_rows`.
    """
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


class SandboxVerdictsPresentWithCorrectPolarityAndEmitter(unittest.TestCase):
    """Each of the three SANDBOX_* verdicts exists with the correct shape."""

    def setUp(self):
        rows = _parse_catalog_rows()
        self.by_verdict = {r["verdict"]: r for r in rows}

    def _assert_row(self, name, polarity):
        self.assertIn(name, self.by_verdict,
                      f"rules/verdict-catalog.md must contain a `{name}` row")
        row = self.by_verdict[name]
        self.assertEqual(row["polarity"], polarity,
                         f"{name} must have polarity={polarity}")
        self.assertIn("sandbox-verify", row["emitters"],
                      f"{name} emitter must be `sandbox-verify`")
        self.assertEqual(row["phase"], "build",
                         f"{name} phase must be `build`")
        return row

    def test_sandbox_verdicts_present_with_correct_polarity_and_emitter(self):
        self._assert_row("SANDBOX_VERIFIED", "success")
        self._assert_row("SANDBOX_FAILED", "failure")
        skipped = self._assert_row("SANDBOX_SKIPPED", "info")
        self.assertIn(
            "no-e2b-token", skipped["branch"],
            "SANDBOX_SKIPPED branch column must enumerate `no-e2b-token` reason")


if __name__ == "__main__":
    unittest.main()
