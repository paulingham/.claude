"""Tier 1 unit tests for slice-c-product-reviewer-gate.

Per plan.md § 3 slice-c Failing test stubs (lines 151-154), four cases:

  1. test_product_reviewer_rejects_when_any_route_exceeds_pixel_diff_threshold
     — route `/dashboard`, ratio 0.08, default 0.02 → REJECTED.
  2. test_product_reviewer_rejects_when_any_route_vlm_verdict_is_FAIL
     — route `/checkout`, vlm_verdict FAIL → REJECTED.
  3. test_product_reviewer_approves_when_all_routes_pass_threshold_and_vlm_PASS
     — all routes < threshold, vlm PASS → APPROVED (subject to UX ≥14/20).
  4. test_product_reviewer_dead_producer_trap_door_rejects_when_visual_regression_block_missing
     — no block on frontend-touching change → REJECTED, reason verbatim.

These tests assert documentation contracts on product-reviewer.md and
the product-acceptance SKILL.md spawn prompt — i.e. that the gate-logic
description names the predicates the agent will obey at dispatch time.

Inline rationale: product-reviewer is a read-only agent (its frontmatter
disallows Write/Edit/MultiEdit), so the gate is *spec-as-procedure* — the
markdown IS the contract. Tier 1 assertions verify the contract's text
shape. Tier 2 (integration) runs the real product-reviewer spawn against a
fixture index.json and observes the verdict.
"""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PRODUCT_REVIEWER_AGENT = ROOT / "agents" / "product-reviewer.md"
PRODUCT_ACCEPTANCE_SKILL = ROOT / "skills" / "product-acceptance" / "SKILL.md"


def _read(path):
    return path.read_text(encoding="utf-8")


class ProductReviewerRejectsWhenAnyRouteExceedsPixelDiffThreshold(unittest.TestCase):
    """AC4 #1 — pixel_diff_ratio above threshold ⇒ REJECTED."""

    def test_product_reviewer_rejects_when_any_route_exceeds_pixel_diff_threshold(
        self,
    ):
        body = _read(PRODUCT_REVIEWER_AGENT)
        # The gate logic must REJECT on pixel_diff_ratio above threshold.
        self.assertIn("pixel_diff_ratio", body)
        self.assertIn("threshold", body)
        # The disjunction is the canonical REJECT predicate.
        self.assertIn(
            "pixel_diff_ratio > threshold OR vlm_verdict == FAIL",
            body,
            "AC4: product-reviewer.md must document the REJECT predicate",
        )

    def test_gate_logic_names_reject_action_on_threshold_breach(self):
        body = _read(PRODUCT_REVIEWER_AGENT)
        # Locate the visual_regression machine pre-check phrase, then look
        # forward for the REJECT keyword.
        gate_idx = body.find("visual_regression machine pre-check")
        self.assertGreater(
            gate_idx,
            -1,
            "AC4: gate-logic anchor `visual_regression machine pre-check` "
            "missing from product-reviewer.md",
        )
        # The next ~1500 chars after the anchor must name REJECT and the
        # threshold predicate.
        gate_section = body[gate_idx : gate_idx + 1500]
        self.assertIn(
            "REJECT",
            gate_section,
            "AC4: gate-logic section must name REJECT action",
        )


class ProductReviewerRejectsWhenAnyRouteVlmVerdictIsFAIL(unittest.TestCase):
    """AC4 #2 — vlm_verdict == FAIL ⇒ REJECTED."""

    def test_product_reviewer_rejects_when_any_route_vlm_verdict_is_FAIL(self):
        body = _read(PRODUCT_REVIEWER_AGENT)
        # `vlm_verdict == FAIL` is the second half of the REJECT predicate.
        self.assertIn("vlm_verdict", body)
        self.assertIn("FAIL", body)
        # Pinned exact disjunction.
        self.assertIn("pixel_diff_ratio > threshold OR vlm_verdict == FAIL", body)


class ProductReviewerApprovesWhenAllRoutesPassThresholdAndVlmPASS(unittest.TestCase):
    """AC4 #3 — all routes pass threshold + vlm PASS ⇒ APPROVED (UX ≥14/20)."""

    def test_product_reviewer_approves_when_all_routes_pass_threshold_and_vlm_PASS(
        self,
    ):
        body = _read(PRODUCT_REVIEWER_AGENT)
        # APPROVED outcome must remain the documented happy path.
        self.assertIn(
            "APPROVED",
            body,
            "AC4: product-reviewer.md must continue to document APPROVED outcome",
        )
        # UX ≥14/20 gate is documented in § 2 UX Heuristic Evaluation.
        self.assertIn(
            "14/20",
            body,
            "AC4: UX heuristic ≥14/20 gate must remain documented as APPROVED prerequisite",
        )

    def test_gate_does_not_short_circuit_to_approve_when_all_routes_pass(self):
        """Negative spec: the gate must NOT bypass the UX heuristic on
        clean visual-regression. Visual regression is a *pre-check* — its
        passing is necessary but not sufficient for APPROVED."""
        body = _read(PRODUCT_REVIEWER_AGENT)
        # The pre-check phrase explicitly frames this as a precondition,
        # not a sufficient condition.
        self.assertIn(
            "machine pre-check",
            body,
            "AC4: `machine pre-check` framing prevents short-circuit-to-approve "
            "(visual_regression PASS is necessary, not sufficient)",
        )


class ProductReviewerDeadProducerTrapDoorRejectsWhenVisualRegressionBlockMissing(
    unittest.TestCase
):
    """AC4 #4 — dead-producer trap-door: missing block ⇒ REJECTED."""

    def test_product_reviewer_dead_producer_trap_door_rejects_when_visual_regression_block_missing(
        self,
    ):
        body = _read(PRODUCT_REVIEWER_AGENT)
        # Verbatim reason-string from plan § Slice slice-c-product-reviewer-gate.
        expected_reason = (
            "visual_regression block missing — producer (vlm-critic) did not run"
        )
        self.assertIn(
            expected_reason,
            body,
            "AC4 trap-door: product-reviewer.md must document the verbatim "
            f"reason `{expected_reason}` for missing-block REJECT",
        )

    def test_gate_logic_treats_missing_block_as_vlm_blocked(self):
        body = _read(PRODUCT_REVIEWER_AGENT)
        # The fail-closed treatment must be documented: missing-block ⇒
        # vlm_verdict == BLOCKED.
        self.assertIn(
            "BLOCKED",
            body,
            "AC4 trap-door: missing block must be treated as BLOCKED",
        )

    def test_gate_logic_qualifies_trap_door_to_frontend_touching_changes(self):
        body = _read(PRODUCT_REVIEWER_AGENT)
        # The trap-door applies only on frontend-touching changes (non-frontend
        # PRs do not produce a visual_regression block at all).
        self.assertIn(
            "frontend-touching",
            body,
            "AC4 trap-door: fail-closed scope must be qualified to "
            "frontend-touching changes",
        )


class ProductAcceptanceSkillSpawnPromptCarriesGateLanguage(unittest.TestCase):
    """Cross-cutting — the SKILL.md spawn prompt must carry the same gate
    language so the dispatched product-reviewer sees it at call time, not
    only on agent-startup read.
    """

    def test_skill_spawn_prompt_mentions_visual_regression_block(self):
        body = _read(PRODUCT_ACCEPTANCE_SKILL)
        # The spawn prompt should mention the index.json visual_regression
        # block check so the agent doesn't miss it.
        self.assertIn("visual_regression", body)

    def test_skill_spawn_prompt_carries_reject_predicate(self):
        body = _read(PRODUCT_ACCEPTANCE_SKILL)
        self.assertIn("pixel_diff_ratio > threshold OR vlm_verdict == FAIL", body)


if __name__ == "__main__":
    unittest.main()
