"""Tests for eval baseline and rollout gate skill — AC24-AC26.

AC24: eval/baselines/swe-pruner-advisory-context.md exists with required frontmatter.
AC25: skills/swe-pruner-rollout-gate/SKILL.md names all three verdicts, thresholds,
      review cadence with forcing trigger.
AC26: SKILL.md states DEFERRED and names flip surface.
"""
import re
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]

EVAL_BASELINE = _REPO_ROOT / "eval" / "baselines" / "swe-pruner-advisory-context.md"
ROLLOUT_GATE = _REPO_ROOT / "skills" / "swe-pruner-rollout-gate" / "SKILL.md"


class TestEvalBaseline(unittest.TestCase):
    """AC24: Eval baseline file has required fields."""

    def test_eval_baseline_file_exists(self):
        self.assertTrue(EVAL_BASELINE.exists(),
                        f"Missing: {EVAL_BASELINE}")

    def test_eval_baseline_has_advisory_mode_true(self):
        content = EVAL_BASELINE.read_text()
        self.assertIn("advisory_mode: true", content,
                      "eval baseline missing 'advisory_mode: true'")

    def test_eval_baseline_records_quantitative_pass_rate(self):
        """Baseline MUST carry eval_pass_rate + eval_suite + eval_n (AC24 strengthened)."""
        content = EVAL_BASELINE.read_text()
        self.assertIn("eval_pass_rate", content,
                      "eval baseline missing 'eval_pass_rate'")
        self.assertIn("eval_suite", content,
                      "eval baseline missing 'eval_suite'")
        self.assertIn("eval_n", content,
                      "eval baseline missing 'eval_n'")

    def test_eval_baseline_states_option_a_scope(self):
        """Baseline must contain the Option-A scope transparency note."""
        content = EVAL_BASELINE.read_text()
        # Must mention that it operates on spawn prompt, NOT source files
        self.assertRegex(
            content,
            r"(spawn prompt|tool_input\.prompt|orchestrator-assembled)",
            "eval baseline missing Option-A scope transparency note"
        )


class TestRolloutGateSkill(unittest.TestCase):
    """AC25-AC26: SKILL.md has all required content."""

    def test_rollout_gate_skill_exists(self):
        self.assertTrue(ROLLOUT_GATE.exists(),
                        f"Missing: {ROLLOUT_GATE}")

    def test_rollout_gate_skill_names_all_three_verdicts(self):
        content = ROLLOUT_GATE.read_text()
        self.assertIn("ROLLOUT_GATE_PASS", content,
                      "SKILL.md missing ROLLOUT_GATE_PASS verdict")
        self.assertIn("ROLLOUT_GATE_FAIL", content,
                      "SKILL.md missing ROLLOUT_GATE_FAIL verdict")
        self.assertIn("INSUFFICIENT_DATA", content,
                      "SKILL.md missing INSUFFICIENT_DATA verdict")

    def test_rollout_gate_skill_names_threshold_values(self):
        content = ROLLOUT_GATE.read_text()
        # Plan specifies: 5% token_delta, 50 pipelines, 14 days
        self.assertIn("5%", content,
                      "SKILL.md missing 5% token_delta threshold")
        self.assertIn("50", content,
                      "SKILL.md missing 50 pipelines threshold")
        self.assertIn("14", content,
                      "SKILL.md missing 14 days threshold")

    def test_rollout_gate_skill_names_review_cadence(self):
        """AC25 strengthened: must name forcing trigger with specific numbers."""
        content = ROLLOUT_GATE.read_text()
        # Must name the review cadence with >= 50 pipelines / >= 14 days
        self.assertRegex(
            content,
            r"(>=\s*50|50\s*pipeline|after.*50)",
            "SKILL.md missing 50-pipeline review cadence trigger"
        )
        self.assertRegex(
            content,
            r"(>=\s*14|14\s*day|after.*14)",
            "SKILL.md missing 14-day review cadence trigger"
        )
        # Must name the skill invocation
        self.assertIn("/harness:swe-pruner-rollout-gate", content,
                      "SKILL.md missing /harness:swe-pruner-rollout-gate invocation reference")

    def test_rollout_gate_skill_states_deferred(self):
        """AC26: SKILL.md states DEFERRED."""
        content = ROLLOUT_GATE.read_text()
        self.assertIn("DEFERRED", content,
                      "SKILL.md missing DEFERRED state declaration")

    def test_rollout_gate_flip_surface_named(self):
        """AC26: flip surface must be named (pre-agent-swe-pruner.sh)."""
        content = ROLLOUT_GATE.read_text()
        self.assertIn("pre-agent-swe-pruner.sh", content,
                      "SKILL.md missing flip surface name (pre-agent-swe-pruner.sh)")


if __name__ == "__main__":
    unittest.main()
