"""Slice slice-c-product-reviewer-gate — Tier 0 contract tests.

Per plan.md § 3 Slice slice-c-product-reviewer-gate Tier 0 Contract Assertions
(lines 142-145), three assertions:

  1. `agents/product-reviewer.md` Acceptance Review section contains the
     verbatim literal phrase `visual_regression machine pre-check`
     (SE-4 pin — fixed-string grep, not "or equivalent").
  2. `skills/product-acceptance/SKILL.md` spawn prompt L54-60 contains the
     verbatim literal phrase `visual_regression` AND the verbatim literal
     phrase `pixel_diff_ratio > threshold OR vlm_verdict == FAIL`
     (SE-4 pin — both pinned as fixed-string assertions).
  3. Producer-presence assertion: if a fixture index.json lacks the
     `visual_regression` block on a frontend-touching change,
     product-reviewer's gate logic FAILS-CLOSED (treats absence as
     `vlm_verdict == BLOCKED`, returns REJECTED with reason
     `visual_regression block missing — producer (vlm-critic) did not run`).
     This is the dead-producer trap-door — AC3+AC4 atomicity guard
     (PR #105 anti-pattern prevention).

The third assertion is a markdown-contract check: the gate logic
documented in product-reviewer.md must name BOTH the missing-block
condition AND the reason-string verbatim, so the dispatched product-reviewer
spawn obeys the fail-closed semantics. Behavioural verification of the
gate against a real index.json fixture lives in Tier 2 at
`tests/integration/test_product_reviewer_index_json_consumer.py`.
"""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent.parent
PRODUCT_REVIEWER_AGENT = ROOT / "agents" / "product-reviewer.md"
PRODUCT_ACCEPTANCE_SKILL = ROOT / "skills" / "product-acceptance" / "SKILL.md"


def _read(path):
    return path.read_text(encoding="utf-8")


def _slice_l54_60(body):
    """Return lines 54..60 inclusive of body as a single string.

    Per plan.md § Slice slice-c-product-reviewer-gate (line 144), the SE-4
    pin targets `skills/product-acceptance/SKILL.md` spawn prompt L54-60.
    The pin asserts the literal phrases appear in this exact line range
    rather than anywhere in the file — that locates the gate language
    inside the actual product-reviewer spawn prompt, not e.g. a docstring.
    """
    lines = body.splitlines()
    # 1-indexed lines 54..60 inclusive.
    return "\n".join(lines[53:60])


class ProductReviewerAgentMarkdownContainsVisualRegressionMachinePreCheckPhrase(
    unittest.TestCase
):
    """Tier 0 #1 — SE-4 verbatim pin on product-reviewer.md."""

    def test_product_reviewer_agent_md_file_exists(self):
        self.assertTrue(
            PRODUCT_REVIEWER_AGENT.exists(),
            f"{PRODUCT_REVIEWER_AGENT} must exist (slice-c AC4)",
        )

    def test_product_reviewer_md_contains_visual_regression_machine_pre_check_phrase(
        self,
    ):
        body = _read(PRODUCT_REVIEWER_AGENT)
        # SE-4 pin: literal fixed-string grep.
        self.assertIn(
            "visual_regression machine pre-check",
            body,
            "SE-4 pin: product-reviewer.md must contain the verbatim phrase "
            "`visual_regression machine pre-check`",
        )

    def test_phrase_lives_under_acceptance_review_outcome_section(self):
        """The phrase must live under the Acceptance Review § Outcome
        section so the agent runs it at story-acceptance time, not at
        plan-validation time."""
        body = _read(PRODUCT_REVIEWER_AGENT)
        # Locate the Acceptance Review heading and the Outcome subsection.
        ar_idx = body.find("## Acceptance Review")
        self.assertGreater(
            ar_idx,
            -1,
            "product-reviewer.md must have a `## Acceptance Review` section",
        )
        # Slice from Acceptance Review onwards.
        after_ar = body[ar_idx:]
        outcome_idx = after_ar.find("### Outcome")
        self.assertGreater(
            outcome_idx,
            -1,
            "product-reviewer.md `## Acceptance Review` must contain an "
            "`### Outcome` subsection",
        )
        # The phrase must appear after the Outcome heading.
        outcome_body = after_ar[outcome_idx:]
        self.assertIn(
            "visual_regression machine pre-check",
            outcome_body,
            "SE-4 pin: `visual_regression machine pre-check` must appear "
            "under Acceptance Review § Outcome",
        )


class ProductAcceptanceSkillL54_60ContainsPixelDiffThresholdPin(unittest.TestCase):
    """Tier 0 #2 — SE-4 verbatim pin on skills/product-acceptance/SKILL.md L54-60."""

    def test_product_acceptance_skill_md_file_exists(self):
        self.assertTrue(
            PRODUCT_ACCEPTANCE_SKILL.exists(),
            f"{PRODUCT_ACCEPTANCE_SKILL} must exist (slice-c AC4)",
        )

    def test_product_acceptance_skill_l54_60_contains_visual_regression_token(self):
        body = _read(PRODUCT_ACCEPTANCE_SKILL)
        window = _slice_l54_60(body)
        # SE-4 pin: literal fixed-string grep against L54-60 inclusive.
        self.assertIn(
            "visual_regression",
            window,
            "SE-4 pin: SKILL.md L54-60 must contain the literal token "
            "`visual_regression`; current window:\n" + window,
        )

    def test_product_acceptance_skill_l54_60_contains_pixel_diff_threshold_pin(
        self,
    ):
        body = _read(PRODUCT_ACCEPTANCE_SKILL)
        window = _slice_l54_60(body)
        # SE-4 pin: literal fixed-string grep against L54-60 inclusive.
        self.assertIn(
            "pixel_diff_ratio > threshold OR vlm_verdict == FAIL",
            window,
            "SE-4 pin: SKILL.md L54-60 must contain the verbatim phrase "
            "`pixel_diff_ratio > threshold OR vlm_verdict == FAIL`; "
            "current window:\n" + window,
        )


class IndexJsonVisualRegressionBlockIsRequiredNotOptional(unittest.TestCase):
    """Tier 0 #3 — dead-producer trap-door (AC3+AC4 atomicity guard).

    Asserts the product-reviewer.md gate-logic markdown documents the
    fail-closed semantics for missing-block on a frontend-touching change.
    Behavioural verification of the gate against a real index.json fixture
    is in Tier 2.
    """

    def test_index_json_visual_regression_block_is_required_not_optional(self):
        body = _read(PRODUCT_REVIEWER_AGENT)
        # The gate logic must document missing-block fail-closed behaviour.
        # Verbatim reason-string from plan § Slice slice-c-product-reviewer-gate.
        expected_reason = (
            "visual_regression block missing — producer (vlm-critic) did not run"
        )
        self.assertIn(
            expected_reason,
            body,
            "Dead-producer trap-door: product-reviewer.md must document the "
            f"verbatim reason string `{expected_reason}`",
        )

    def test_gate_logic_names_blocked_verdict_for_missing_block(self):
        body = _read(PRODUCT_REVIEWER_AGENT)
        # Fail-closed semantics: missing block ⇒ treat as vlm_verdict == BLOCKED.
        self.assertIn(
            "BLOCKED",
            body,
            "Dead-producer trap-door: product-reviewer.md must name "
            "the BLOCKED pseudo-verdict for missing-block treatment",
        )

    def test_gate_logic_names_index_json_read_target(self):
        body = _read(PRODUCT_REVIEWER_AGENT)
        # The agent must read index.json at the canonical path.
        self.assertIn(
            "pipeline-state/{task-id}/design-qc/index.json",
            body,
            "Gate logic: product-reviewer.md must name the canonical "
            "index.json path",
        )

    def test_gate_logic_rejects_on_threshold_or_vlm_fail(self):
        body = _read(PRODUCT_REVIEWER_AGENT)
        # The verbatim disjunction that the spawn prompt also pins.
        self.assertIn(
            "pixel_diff_ratio > threshold OR vlm_verdict == FAIL",
            body,
            "Gate logic: product-reviewer.md must document the REJECT "
            "predicate `pixel_diff_ratio > threshold OR vlm_verdict == FAIL`",
        )


if __name__ == "__main__":
    unittest.main()
