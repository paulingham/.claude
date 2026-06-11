"""Slice C — Iron Law 3 protected-location doc update verification.

E1: rules/core.md line 11 (Iron Law 3) must contain:
    - The verbatim headline "THE ORCHESTRATOR NEVER WRITES SOURCE CODE."
    - The word "net-new" (new concept introduced by the fix)
    - A reference to "is-protected-path.sh" (enforcement pointer)

E3: T1 dispatch target must say "worktree subagent" not "orchestrator direct edit"
    in both work-class-routing.md and CLAUDE.md.
"""
from pathlib import Path
import re
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent


class IronLaw3UpdatedInRulesCore(unittest.TestCase):
    """E1: rules/core.md Iron Law 3 describes protected-location concept."""

    @classmethod
    def setUpClass(cls):
        cls._text = (REPO_ROOT / "rules" / "core.md").read_text()

    def test_headline_verbatim(self):
        self.assertIn(
            "THE ORCHESTRATOR NEVER WRITES SOURCE CODE.",
            self._text,
            "Iron Law 3 headline must be preserved verbatim",
        )

    def test_net_new_concept_present(self):
        self.assertIn(
            "net-new",
            self._text,
            "Iron Law 3 must mention 'net-new' (the protected-location concept)",
        )

    def test_is_protected_path_reference(self):
        self.assertIn(
            "is-protected-path.sh",
            self._text,
            "Iron Law 3 must reference is-protected-path.sh (enforcement pointer)",
        )


class T1DispatchTargetUpdated(unittest.TestCase):
    """E3: T1 row in work-class-routing.md and CLAUDE.md says 'worktree subagent'."""

    def test_work_class_routing_t1_row(self):
        text = (REPO_ROOT / "protocols" / "work-class-routing.md").read_text()
        # The T1 row must mention worktree subagent (not raw orchestrator direct edit)
        t1_lines = [l for l in text.splitlines() if "T1" in l and "|" in l]
        self.assertTrue(
            any("worktree" in l.lower() for l in t1_lines),
            f"work-class-routing.md T1 row must mention 'worktree'; found: {t1_lines}",
        )

    def test_claude_md_t1_row(self):
        text = (REPO_ROOT / "CLAUDE.md").read_text()
        t1_lines = [l for l in text.splitlines() if "T1" in l and "|" in l]
        self.assertTrue(
            any("worktree" in l.lower() for l in t1_lines),
            f"CLAUDE.md T1 row must mention 'worktree'; found: {t1_lines}",
        )

    def test_work_class_routing_t1_no_longer_says_orchestrator_direct(self):
        text = (REPO_ROOT / "protocols" / "work-class-routing.md").read_text()
        t1_lines = [l for l in text.splitlines() if "T1" in l and "|" in l]
        for line in t1_lines:
            self.assertNotIn(
                "Orchestrator direct edit",
                line,
                f"work-class-routing.md T1 row must not say 'Orchestrator direct edit'; line: {line}",
            )


if __name__ == "__main__":
    unittest.main()
