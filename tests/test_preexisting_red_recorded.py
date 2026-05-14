"""Slice C AC-C4 — pre-existing test red captured at base before edits.

The file at `pipeline-state/promote-advisory-hooks-enforcement/preexisting-red.txt`
is the baseline for distinguishing flip-induced regressions from
pre-existing failures (per session-memory fragility.md:12). Final line
MUST be `EXIT_CODE=<n>` so the format is machine-readable for reviewers.
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RED_FILE = REPO_ROOT / "pipeline-state" \
    / "promote-advisory-hooks-enforcement" / "preexisting-red.txt"


class PreexistingRedFileFormat(unittest.TestCase):
    def test_preexisting_red_file_format(self):
        self.assertTrue(RED_FILE.exists(),
                        f"expected baseline red file at {RED_FILE}")
        lines = [ln for ln in RED_FILE.read_text().splitlines() if ln.strip()]
        self.assertGreater(len(lines), 0, "red file must not be empty")
        # last non-empty line must be EXIT_CODE=<n>
        self.assertRegex(lines[-1], r"^EXIT_CODE=\d+$",
                         f"last line must be EXIT_CODE=<n>; got {lines[-1]!r}")


if __name__ == "__main__":
    unittest.main()
