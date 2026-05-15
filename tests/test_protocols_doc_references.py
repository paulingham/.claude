"""Protocols documentation reference tests (LOW consolidation per plan r2).

Consolidates Slice B and Slice C doc-string assertions into a single file.
Slice B contributes:
  - B.3 (escalated): `protocols/thinking-defaults.md` documents the beta
    header as a consumer-outside-repo escalation AND notes the in-tree wire
    emission shipped on 2026-05-15.
  - B.1 (named deviation): the same doc carries a "Named deviation: high
    floor preserved on review/critic/architect" subsection.

Slice C will extend this file later (skipped now per single-slice scope).
"""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class BetaHeaderConsumerOutsideRepoDocumented(unittest.TestCase):
    """B.3 escalation: the protocol doc names the beta header as a consumer
    outside this repo and notes that in-tree wire emission shipped.
    """

    def test_beta_header_consumer_outside_repo_documented(self):
        path = REPO_ROOT / "protocols" / "thinking-defaults.md"
        body = path.read_text()
        self.assertIn(
            "Beta header — consumer outside repo",
            body,
            "Missing literal 'Beta header — consumer outside repo' clause")
        self.assertIn(
            "in-tree wire emission shipped",
            body,
            "Missing literal 'in-tree wire emission shipped' clause")


class NamedDeviationHighFloorDocumented(unittest.TestCase):
    """B.1 named deviation: the protocol doc carries a subsection that
    explicitly names the high-floor preservation on review/critic/architect.
    """

    def test_named_deviation_high_floor_subsection_present(self):
        path = REPO_ROOT / "protocols" / "thinking-defaults.md"
        body = path.read_text()
        self.assertIn(
            "Named deviation: high floor preserved on "
            "review/critic/architect",
            body,
            "Missing named-deviation subsection literal")


if __name__ == "__main__":
    unittest.main()
