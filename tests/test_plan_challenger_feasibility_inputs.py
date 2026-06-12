"""AC-C1..AC-C3: Plan challenger prompts include feasibility finding wiring.

Asserts that BOTH challenger prompt templates in
`orchestrator/parallel-dispatch-details.md` (Plan Validation Phase Dispatch)
list the Feasibility Finding as an input with the absent-implies-FEASIBLE
fallback, include PLAN_FEASIBILITY_REJECTED in their verdict blocks, and
document overturn in BOTH directions.

Markdown-grep tests — no production code dependency.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DISPATCH = REPO_ROOT / "orchestrator" / "parallel-dispatch-details.md"


def _challenger_block(name: str) -> str:
    """Return the Agent({...}) block for the named challenger prompt."""
    text = DISPATCH.read_text()
    pattern = re.compile(
        r'name:\s+"' + re.escape(name) + r'".*?(?=\nAgent\(\{|\n```\s*\n)',
        re.DOTALL,
    )
    m = pattern.search(text)
    return m.group(0) if m else ""


def _plan_reviewer_block() -> str:
    return _challenger_block("plan-reviewer")


def _plan_engineer_block() -> str:
    return _challenger_block("plan-engineer")


class TestBothChallengersReceiveFeasibilityFinding(unittest.TestCase):
    """AC-C1: Both challenger templates list the Feasibility Finding input
    with the 'absent => implicitly FEASIBLE, still self-check' fallback.
    """

    def _assert_has_feasibility_input(self, block: str, name: str) -> None:
        self.assertTrue(block, f"{name} block not found in dispatch file")
        # Must mention the ## Feasibility Finding section as an input
        self.assertIn(
            "Feasibility Finding",
            block,
            f"{name}: missing 'Feasibility Finding' in Inputs",
        )
        # Must document the absent/implicit-FEASIBLE fallback
        block_lower = block.lower()
        self.assertTrue(
            "absent" in block_lower or "if the section is absent" in block_lower,
            f"{name}: missing absent-implies-FEASIBLE fallback text",
        )
        self.assertIn(
            "FEASIBLE",
            block,
            f"{name}: missing 'FEASIBLE' in Feasibility Finding input description",
        )

    def test_both_challengers_receive_feasibility_finding(self):
        self._assert_has_feasibility_input(_plan_reviewer_block(), "plan-reviewer")
        self._assert_has_feasibility_input(_plan_engineer_block(), "plan-engineer")


class TestChallengerVerdictBlockIncludesFeasibilityRejected(unittest.TestCase):
    """AC-C2: Both templates' verdict blocks include PLAN_FEASIBILITY_REJECTED
    distinct from CHANGES_REQUESTED.
    """

    def _assert_verdict_block(self, block: str, name: str) -> None:
        self.assertTrue(block, f"{name} block not found")
        self.assertIn(
            "PLAN_FEASIBILITY_REJECTED",
            block,
            f"{name}: PLAN_FEASIBILITY_REJECTED missing from verdict block",
        )
        self.assertIn(
            "CHANGES_REQUESTED",
            block,
            f"{name}: CHANGES_REQUESTED missing from verdict block (needed for contrast)",
        )
        # PLAN_FEASIBILITY_REJECTED must appear as a separate verdict entry
        # (not embedded inside the CHANGES_REQUESTED description)
        pfr_pos = block.find("PLAN_FEASIBILITY_REJECTED")
        cr_pos = block.find("CHANGES_REQUESTED")
        self.assertNotEqual(
            pfr_pos, cr_pos,
            f"{name}: PLAN_FEASIBILITY_REJECTED and CHANGES_REQUESTED at same position",
        )

    def test_challenger_verdict_block_includes_feasibility_rejected(self):
        self._assert_verdict_block(_plan_reviewer_block(), "plan-reviewer")
        self._assert_verdict_block(_plan_engineer_block(), "plan-engineer")


class TestOverturnBothDirectionsDocumented(unittest.TestCase):
    """AC-C3: Both templates document overturn BOTH directions:
    (a) architect-FEASIBLE => challenger rejects;
    (b) architect-FEASIBILITY_REJECTED => challenger overturns to APPROVE-with-overturn
        (re-plan trigger).
    """

    def _assert_both_directions(self, block: str, name: str) -> None:
        self.assertTrue(block, f"{name} block not found")
        # Direction (a): architect said FEASIBLE but premise is false -> reject
        has_direction_a = (
            re.search(
                r"architect.*FEASIBLE.*PLAN_FEASIBILITY_REJECTED|"
                r"PLAN_FEASIBILITY_REJECTED.*architect.*FEASIBLE",
                block,
                re.DOTALL | re.IGNORECASE,
            )
            is not None
        )
        self.assertTrue(
            has_direction_a,
            f"{name}: direction (a) missing — architect FEASIBLE but challenger rejects",
        )
        # Direction (b): architect rejected but actually feasible -> APPROVE with overturn note
        has_direction_b = (
            re.search(
                r"architect.*FEASIBILITY_REJECTED.*APPROVE|"
                r"APPROVE.*overturn.*feasib",
                block,
                re.DOTALL | re.IGNORECASE,
            )
            is not None
        )
        self.assertTrue(
            has_direction_b,
            f"{name}: direction (b) missing — architect rejected, challenger overturns to APPROVE",
        )

    def test_overturn_both_directions_documented(self):
        self._assert_both_directions(_plan_reviewer_block(), "plan-reviewer")
        self._assert_both_directions(_plan_engineer_block(), "plan-engineer")


if __name__ == "__main__":
    unittest.main()
