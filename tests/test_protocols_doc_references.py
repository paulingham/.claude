"""Protocols documentation reference tests (LOW consolidation per plan r2).

Consolidates Slice B and Slice C doc-string assertions into a single file.

Slice B contributes:
  - B.3 (escalated): `protocols/thinking-defaults.md` documents the beta
    header as a consumer-outside-repo escalation AND notes the in-tree wire
    emission shipped on 2026-05-15.
  - B.1 (named deviation): the same doc carries a "Named deviation: high
    floor preserved on review/critic/architect" subsection.

Slice C contributes:
  - C.3 (escalated): `protocols/cost-discipline.md` documents the SDK flag
    deferral as a consumer-outside-repo escalation AND references the
    in-tree wire emission shipped.

NOTE: This file is owned by both Slice B and Slice C — both slices append a
literal escalation token to a different protocol doc. The integration branch
keeps both test classes (they are independent doc-prose-reference assertions).
"""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
COST_DISCIPLINE = REPO_ROOT / "protocols" / "cost-discipline.md"


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


class SdkFlagDeferralDocumented(unittest.TestCase):
    def test_sdk_flag_consumer_outside_repo_documented(self):
        text = COST_DISCIPLINE.read_text()
        self.assertIn(
            "SDK flag — consumer outside repo", text,
            "protocols/cost-discipline.md must document the SDK flag deferral "
            "with literal token `SDK flag — consumer outside repo`")
        self.assertIn(
            "in-tree wire emission shipped", text,
            "protocols/cost-discipline.md must reference in-tree wire "
            "emission with literal token `in-tree wire emission shipped`")


if __name__ == "__main__":
    unittest.main()
