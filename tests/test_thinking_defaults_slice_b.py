"""Slice B verification tests — high floor + xhigh promotion preserved.

These tests are VERIFY-ONLY against the existing resolver. They lock the
named-deviation chosen by Slice B (HIGH-PR1 path a): code-reviewer +
security-engineer remain pinned to `high` via `_DOWNGRADE_TO_HIGH`;
architect resolves to `high` via rule 4 fallback when the xhigh gate does
not fire. xhigh promotion semantics (architect@budget=6,
software-engineer@budget=7) are also locked.

If these tests fail, the named deviation has been undone by a future patch
without explicit operator re-acknowledgment — see plan.md frontmatter
`named_deviations` entry `slice-b-high-floor-named-deviation`.
"""
import unittest

from thinking_resolver import resolve


class HighFloorForCodeReviewerSecurityArchitect(unittest.TestCase):
    """B.1 verify-only: code-reviewer + security-engineer remain on `high`
    via the explicit `_DOWNGRADE_TO_HIGH` membership (source=role). Architect
    resolves to `high` via rule 4 fallback when critical=False AND budget<6
    (source=default — architect is NOT in `_DOWNGRADE_TO_HIGH`, but the
    fallback floor still produces `high`).

    Pins the named-deviation: operator AC said "default medium"; reality is
    high floor on these three roles. A change to the floor must be a
    deliberate edit to thinking_role.py + thinking_resolver.py fallback.
    """

    def test_code_reviewer_resolves_to_high_from_role_layer(self):
        result = resolve(
            tool_input={"subagent_type": "code-reviewer"},
            env={}, state={"critical": False, "budget": 0})
        self.assertEqual(result["effort"], "high")
        self.assertEqual(result["source"], "role")

    def test_security_engineer_resolves_to_high_below_gate(self):
        result = resolve(
            tool_input={"subagent_type": "security-engineer"},
            env={}, state={"critical": False, "budget": 0})
        self.assertEqual(result["effort"], "high")
        self.assertEqual(result["source"], "role")

    def test_architect_resolves_to_high_via_fallback(self):
        # architect@critical=False, budget=0 → role layer returns None (gate
        # not fired, not in _DOWNGRADE_TO_HIGH) → rule 4 hardcoded `high`.
        result = resolve(
            tool_input={"subagent_type": "architect"},
            env={}, state={"critical": False, "budget": 0})
        self.assertEqual(result["effort"], "high")
        self.assertEqual(result["source"], "default")


class XhighPromotionPreserved(unittest.TestCase):
    """B.1 verify-only: xhigh gates fire verbatim per PR #124. Locks the
    architect@budget=6 and software-engineer@budget=7 thresholds so the
    named-deviation does not silently erode the gated-promotion mechanism.
    """

    def test_architect_budget_6_yields_xhigh(self):
        result = resolve(
            tool_input={"subagent_type": "architect"},
            env={}, state={"critical": False, "budget": 6})
        self.assertEqual(result["effort"], "xhigh")
        self.assertEqual(result["source"], "role")

    def test_software_engineer_budget_7_yields_xhigh(self):
        result = resolve(
            tool_input={"subagent_type": "software-engineer"},
            env={}, state={"critical": False, "budget": 7})
        self.assertEqual(result["effort"], "xhigh")
        self.assertEqual(result["source"], "role")


if __name__ == "__main__":
    unittest.main()
