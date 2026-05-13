"""AC5, AC6 — Step 5b documents the `## Sandbox Verify` section template
that the build agent writes to `pipeline-state/{task-id}/build.md`.

The template must:
1. Be specified within Step 5b body (AC5).
2. Include a table whose header row carries the columns
   `Test | Worktree | Sandbox | Diff` (AC5).
3. Appear AFTER `## Context for Review` (deterministic location for the
   Story-4 forensics consumer — AC5).
4. Use last-writer-wins semantics so a round-2 sandbox-verify spawn
   overwrites the section produced by round-1 (AC6).
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = (
    REPO_ROOT / "skills" / "build-implementation" / "SKILL.md"
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _step_5b_helpers import step_5b_body  # noqa: E402


class BuildMdSandboxVerifySection(unittest.TestCase):
    """AC5/AC6 contract — body template + section ordering + last-writer-wins."""

    def setUp(self):
        self.text = SKILL_PATH.read_text()
        self.body = step_5b_body(self.text)

    def test_ac5_build_md_sandbox_verify_section_template_present(self):
        """Step 5b body must specify the `## Sandbox Verify` template AND
        the table header columns `Test | Worktree | Sandbox | Diff`."""
        self.assertNotEqual(self.body, "", "Step 5b heading not found")
        self.assertIn(
            "## Sandbox Verify",
            self.body,
            "Step 5b body must specify the `## Sandbox Verify` section "
            "template the build agent writes to build.md (AC5)")
        # Table header columns — pinned byte-for-byte so the Story-4
        # forensics consumer can rely on the column layout.
        self.assertIn(
            "Test | Worktree | Sandbox | Diff",
            self.body,
            "Step 5b body must specify the table header columns "
            "`Test | Worktree | Sandbox | Diff` (AC5)")

    def test_ac5_section_order_after_context_for_review(self):
        """The template must position `## Sandbox Verify` AFTER
        `## Context for Review` so Story-4 forensics can locate the block
        deterministically."""
        # Section-order contract is encoded in the SKILL.md text as a whole
        # (the section ordering documentation lives near the `## Context
        # for Review` doc); look up the index of both markers in the FULL
        # text rather than just Step 5b body.
        ctx_idx = self.text.find("## Context for Review")
        sbx_template_idx = self.text.find("## Sandbox Verify")
        self.assertGreater(
            ctx_idx, -1,
            "`## Context for Review` documentation must remain in SKILL.md")
        self.assertGreater(
            sbx_template_idx, ctx_idx,
            "`## Sandbox Verify` template must be documented AFTER "
            "`## Context for Review` (AC5 — deterministic forensics order)")

    def test_ac6_round_2_section_overwrite_semantics_documented(self):
        """Step 5b body must state the last-writer-wins semantics — round-2
        sandbox-verify output overwrites the round-1 `## Sandbox Verify`
        section (AC6)."""
        self.assertNotEqual(self.body, "", "Step 5b heading not found")
        self.assertIn(
            "last-writer-wins",
            self.body,
            "Step 5b body must document `last-writer-wins` overwrite "
            "semantics so a round-2 sandbox-verify spawn replaces the "
            "round-1 section in build.md (AC6)")


if __name__ == "__main__":
    unittest.main()
