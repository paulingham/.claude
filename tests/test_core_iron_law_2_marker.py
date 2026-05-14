"""Slice 1: rules/core.md Iron Law 2 (line 10) gains an append-only parenthetical
naming the new hook and the Path-B → Path-A flip target.

The base sentence MUST be preserved verbatim (append-only edit). The parenthetical
must name:
  - the hook path `hooks/verification-freshness-guard.sh`
  - the version stamp v2.1.141 (intake discrepancy #1)
  - the `permissionDecision` flip surface
"""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CORE = REPO_ROOT / "rules" / "core.md"

BASE_TEXT = (
    "**NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE.** "
    "Stale test output from earlier in the session is not evidence — "
    "re-run before claiming done."
)


class IronLaw2Marker(unittest.TestCase):
    def test_iron_law_2_references_hook_at_v2_1_141(self):
        text = CORE.read_text()
        self.assertIn("hooks/verification-freshness-guard.sh", text)
        self.assertIn("v2.1.141", text)
        self.assertIn("permissionDecision", text)
        self.assertIn("log-only", text)

    def test_iron_law_2_existing_text_unchanged(self):
        """Append-only edit — the original Iron Law 2 sentence must still be
        present verbatim (no replacement, no rewording)."""
        text = CORE.read_text()
        self.assertIn(BASE_TEXT, text,
                      "Original Iron Law 2 sentence must be preserved verbatim")


if __name__ == "__main__":
    unittest.main()
