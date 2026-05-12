"""AC1, AC2, AC3, AC6 — body content of Step 5b in build-implementation
SKILL.md.

Each test reads the SKILL.md body and asserts a load-bearing phrase or
behavioral contract is documented. These are prose-byte-pinned assertions;
when the SKILL.md prose changes the discriminator string MUST stay byte-
identical.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = (
    REPO_ROOT / "skills" / "build-implementation" / "SKILL.md"
)

# Conftest prepends `hooks/_lib`; we need `tests/` for the shared helper.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _step_5b_helpers import step_5b_body  # noqa: E402


class Step5bBodyContract(unittest.TestCase):
    """AC1, AC2, AC3, AC6 — prose-byte-pin assertions on Step 5b body."""

    def setUp(self):
        self.text = SKILL_PATH.read_text()
        self.body = step_5b_body(self.text)

    def test_ac1_build_complete_precondition_includes_sandbox_verdict(self):
        """BUILD_COMPLETE bullet in `## Verdict` must require Step 5b verdict.

        The bullet must contain the exact phrase
        `AND sandbox-verify returned SANDBOX_VERIFIED or SANDBOX_SKIPPED`.
        """
        self.assertIn(
            "AND sandbox-verify returned "
            "SANDBOX_VERIFIED or SANDBOX_SKIPPED",
            self.text,
            "## Verdict BUILD_COMPLETE bullet must require Step 5b verdict "
            "(SANDBOX_VERIFIED or SANDBOX_SKIPPED)")

    def test_ac1_step_5b_dispatches_sandbox_verify_skill(self):
        """Step 5b body must reference `/sandbox-verify` invocation
        AND the `sandbox-verify-engineer` agent."""
        self.assertNotEqual(
            self.body, "",
            "Step 5b heading not found in build-implementation SKILL.md")
        self.assertIn(
            "/sandbox-verify",
            self.body,
            "Step 5b body must reference `/sandbox-verify` skill dispatch")
        self.assertIn(
            "sandbox-verify-engineer",
            self.body,
            "Step 5b body must reference `sandbox-verify-engineer` agent")

    def test_ac2_sandbox_failed_routes_to_fix_engineer_same_worktree(self):
        """Step 5b body must document SANDBOX_FAILED → fix-engineer on the
        SAME worktree, with the combined 2-round cap."""
        self.assertNotEqual(self.body, "", "Step 5b heading not found")
        self.assertIn(
            "fix-engineer",
            self.body,
            "Step 5b body must reference `fix-engineer` for SANDBOX_FAILED")
        self.assertIn(
            "same worktree",
            self.body,
            "Step 5b body must specify the SAME worktree contract "
            "for fix-engineer dispatch")
        # Accept either rendering of the cap phrase: prose may say
        # "max 2 rounds" or "maximum of 2 rounds" — both encode the cap.
        self.assertTrue(
            "2 rounds" in self.body,
            "Step 5b body must enforce a 2-round combined cap")

    def test_ac2_combined_round_budget_documented_explicitly(self):
        """The combined-budget contract must use the exact phrase
        `combined with Step 5` — the lockstep with Step 5's standalone
        max-2-rounds rule is too easy to misread without an explicit token."""
        self.assertIn(
            "combined with Step 5",
            self.body,
            "Step 5b body must use the exact phrase `combined with Step 5` "
            "so the shared round budget is unambiguous (AC2)")

    def test_ac3_docs_only_skipped_with_no_testable_changes(self):
        """SANDBOX_SKIPPED reason `no-testable-changes` must be documented
        in Step 5b body as the docs-only path."""
        self.assertNotEqual(self.body, "", "Step 5b heading not found")
        self.assertIn(
            "SANDBOX_SKIPPED",
            self.body,
            "Step 5b body must enumerate the SANDBOX_SKIPPED verdict")
        self.assertIn(
            "no-testable-changes",
            self.body,
            "Step 5b body must document `no-testable-changes` skip reason "
            "(docs-only / no src/ change path) per AC3")

    def test_ac6_failure_case_round_2_escalation_path_documented(self):
        """AC6 — both round-2 success AND round-2 failure must be addressed.

        Round-2 success → final section reflects round-2 outcome. Round-2
        failure → escalation (round 3+ goes to the user). The body must
        cover both branches explicitly.
        """
        self.assertNotEqual(self.body, "", "Step 5b heading not found")
        self.assertIn(
            "escalate",
            self.body,
            "Step 5b body must document round-2-failure escalation path "
            "(round 3+ → user) per AC6")


if __name__ == "__main__":
    unittest.main()
