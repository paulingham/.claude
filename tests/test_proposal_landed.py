"""Slice 1: proposal file lands under protocols/_proposals/ with required sections.

The proposal (originally PR #125) ships in the same diff as the implementation,
plus two new sections required by plan-validation round 2:
  - § Promotion Criterion (HIGH-PR2 + NEW-MEDIUM-PR1 tightening)
  - § Operator Copy (MEDIUM-PR1 + NEW-LOW-PR1 tightening)
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PROPOSAL = REPO_ROOT / "protocols" / "_proposals" / "2026-05-14-iron-law-2-freshness-hook.md"


class ProposalLanded(unittest.TestCase):
    def test_proposal_file_exists_at_expected_path(self):
        self.assertTrue(PROPOSAL.exists(),
                        f"expected proposal at {PROPOSAL}")
        self.assertGreater(PROPOSAL.stat().st_size, 0,
                           "proposal must be non-empty")

    def test_proposal_file_contains_spec_anchor(self):
        text = PROPOSAL.read_text()
        self.assertIn("verification-freshness-guard.sh", text,
                      "proposal must reference the hook file by name")


class ProposalRound2Refinements(unittest.TestCase):
    """NEW sections added in S1 per plan.md AC1.3 / AC1.4 and
    plan-validation round 2 refinements NEW-MEDIUM-PR1 / NEW-LOW-PR1 / NEW-LOW-PR2."""

    def test_proposal_contains_promotion_criterion_section(self):
        text = PROPOSAL.read_text()
        self.assertIn("## Promotion Criterion", text)
        # Three clauses required: 14-day/50-pipeline soak,
        # permissionDecision schema exposure, operator review.
        self.assertIn("14 days", text)
        self.assertIn("50 pipelines", text)
        self.assertIn("permissionDecision", text)
        self.assertIn("operator review", text.lower())
        # NEW-MEDIUM-PR1: tightened wording — "0 would_block records of any kind"
        # not the original "0 unexpected" phrasing.
        self.assertIn("0 `would_block` records of any kind", text,
                      "Promotion Criterion clause (a) must use the tightened "
                      "NEW-MEDIUM-PR1 wording.")

    def test_proposal_contains_operator_copy_table_9_rows(self):
        text = PROPOSAL.read_text()
        self.assertIn("## Operator Copy", text)
        # Find the Operator Copy section header and count data rows in the
        # table that follows (header + separator + data rows).
        idx = text.index("## Operator Copy")
        # Limit scan to the next ## section to avoid false matches.
        next_heading = re.search(r"\n## ", text[idx + 1:])
        section = text[idx:idx + 1 + next_heading.start()] if next_heading else text[idx:]
        rows = [ln for ln in section.splitlines()
                if ln.startswith("|") and not ln.startswith("|---") and "reason" not in ln.split("|")[1].strip()]
        # 9 data rows: fresh, state_file_missing, git_head_mismatch, hard_staleness,
        # no_worktree_resolvable, sandbox_staleness, state_file_parse_error,
        # git_timeout, invalid_task_id (LOW-SEC2).
        self.assertEqual(len(rows), 9,
                         f"Operator Copy table must have 9 data rows, found {len(rows)}")
        # LOW-SEC2: invalid_task_id row must be present with the validation regex.
        itid_row = [r for r in rows if "invalid_task_id" in r]
        self.assertEqual(len(itid_row), 1)
        self.assertIn("[a-z0-9_-]+", itid_row[0])
        # NEW-LOW-PR1: no_worktree_resolvable recovery_action must give a runnable
        # next step (not just a pointer).
        nwr_row = [r for r in rows if "no_worktree_resolvable" in r]
        self.assertEqual(len(nwr_row), 1)
        self.assertIn("$CLAUDE_WORKTREE_PATH", nwr_row[0])

    def test_proposal_out_of_scope_includes_dispatch_site_test_bullet(self):
        """NEW-LOW-PR2: behavioural test for orchestrator dispatch-site env
        propagation is explicitly OOS — covered by forensics in the soak."""
        text = PROPOSAL.read_text()
        self.assertIn("## Out of Scope", text)
        self.assertIn("dispatch site sets `$CLAUDE_WORKTREE_PATH`", text)


if __name__ == "__main__":
    unittest.main()
