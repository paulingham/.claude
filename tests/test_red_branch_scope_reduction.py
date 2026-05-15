"""Slice C AC-C3 (RED-conditional) — protocols/autonomous-intelligence.md
cites probe-result.md as evidence of the schema gap.

Activated when probe verdict is RED: the protocol must document why
mutation-semantic flips remain advisory so future architect work picks
up the schema-gap reasoning without re-deriving it.
"""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class RedBranchDocumentsSchemaGap(unittest.TestCase):
    def test_red_branch_documents_schema_gap(self):
        body = (REPO_ROOT / "protocols" / "autonomous-intelligence.md").read_text()
        self.assertIn("probe-result.md", body,
                      "autonomous-intelligence.md must reference probe-result.md "
                      "to document the schema-gap evidence")


if __name__ == "__main__":
    unittest.main()
