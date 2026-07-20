"""Slice C — Iron Law 3 protected-location doc update verification.

E1: rules/core.md line 11 (Iron Law 3) must contain:
    - The verbatim headline "THE ORCHESTRATOR NEVER WRITES SOURCE CODE."
    - The word "net-new" (new concept introduced by the fix)
    - A reference to "is-protected-path.sh" (enforcement pointer)

E3: the tracked-doc-edit dispatch target must say "worktree subagent" not
    "orchestrator direct edit" in both work-class-routing.md and CLAUDE.md.
    Phase D Wave 2 retired the literal "T1" row label (tier -> gear
    vocabulary flip); the PAIR row's tracked-doc-edit dispatch capability
    is the successor surface these assertions pin.
"""
from pathlib import Path
import re
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent


class IronLaw3UpdatedInRulesCore(unittest.TestCase):
    """E1: rules/safety.md Iron Law 3 describes protected-location concept.

    Law 3 lives in rules/safety.md after the Phase B gear-tier split
    (rules/core.md is now a thin @-include index)."""

    @classmethod
    def setUpClass(cls):
        cls._text = (REPO_ROOT / "rules" / "safety.md").read_text()

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
    """E3: the tracked-doc-edit dispatch capability in work-class-routing.md
    and CLAUDE.md says 'worktree subagent'.

    Phase D Wave 2 note: the literal "T1" row label was retired when the
    tier vocabulary flipped to gears. The tracked-doc-edit capability now
    lives inside the PAIR gear's sub-behaviour table/row, not a standalone
    "T1" row — these assertions locate it by the "doc" + "worktree" phrase
    pair instead of by tier label.
    """

    def test_work_class_routing_doc_edit_row(self):
        text = (REPO_ROOT / "protocols" / "work-class-routing.md").read_text()
        # The tracked-doc-edit capability must mention worktree subagent
        # (not raw orchestrator direct edit).
        doc_lines = [
            l for l in text.splitlines()
            if "|" in l and "doc" in l.lower() and "worktree" in l.lower()
        ]
        self.assertTrue(
            doc_lines,
            "work-class-routing.md must have a tracked-doc-edit row/line "
            "mentioning 'worktree'",
        )

    def test_claude_md_doc_edit_row(self):
        text = (REPO_ROOT / "CLAUDE.md").read_text()
        doc_lines = [
            l for l in text.splitlines()
            if "|" in l and "doc" in l.lower() and "worktree" in l.lower()
        ]
        self.assertTrue(
            doc_lines,
            "CLAUDE.md must have a tracked-doc-edit row/line mentioning "
            "'worktree'",
        )

    def test_work_class_routing_no_longer_says_orchestrator_direct(self):
        text = (REPO_ROOT / "protocols" / "work-class-routing.md").read_text()
        doc_lines = [
            l for l in text.splitlines()
            if "|" in l and "doc" in l.lower()
        ]
        for line in doc_lines:
            self.assertNotIn(
                "Orchestrator direct edit",
                line,
                "work-class-routing.md doc-edit row must not say "
                f"'Orchestrator direct edit'; line: {line}",
            )


if __name__ == "__main__":
    unittest.main()
