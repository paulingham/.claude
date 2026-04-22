"""Harness-level tests for Slice 5c state symlinks.

Asserts shape, exported helpers, and knowledge doc contents. Real behavior
tests live in tests/shell/state-symlink.bats.
"""
from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LIB_FILE = REPO_ROOT / "scripts" / "_lib" / "state-symlink.sh"
KNOWLEDGE_DOC = REPO_ROOT / "knowledge" / "session-isolation-patterns.md"


class StateSymlinkShape(unittest.TestCase):
    def test_state_symlink_sh_under_40_lines(self) -> None:
        lines = LIB_FILE.read_text().splitlines()
        self.assertLessEqual(len(lines), 40, f"state-symlink.sh has {len(lines)} lines")

    def test_exports_apply_and_verify(self) -> None:
        body = LIB_FILE.read_text()
        self.assertIn("_apply_state_symlinks()", body)
        self.assertIn("_verify_symlinks()", body)
        self.assertIn("_is_canonical_harness()", body)

    def test_bash_n_clean(self) -> None:
        result = subprocess.run(
            ["bash", "-n", str(LIB_FILE)], capture_output=True, text=True, check=False
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)


class SessionIsolationKnowledge(unittest.TestCase):
    REQUIRED_SECTIONS = (
        "Worktree model",
        "Per-branch vs shared state",
        "Safety considerations",
        "When to use --no-state-share",
        "Rollback impact",
    )
    VERBATIM_MITIGATION = (
        'for d in session-memory learning manifests; '
        'do ln -sfn "$HOME/.claude/$d" '
        '"$(git rev-parse --show-toplevel)/$d"; done && '
        'ln -sfn "$HOME/.claude/db/memory.sqlite" '
        '"$(git rev-parse --show-toplevel)/db/memory.sqlite"'
    )

    def test_knowledge_doc_exists(self) -> None:
        self.assertTrue(KNOWLEDGE_DOC.exists(), f"missing: {KNOWLEDGE_DOC}")

    def test_all_required_sections_present(self) -> None:
        body = KNOWLEDGE_DOC.read_text()
        for section in self.REQUIRED_SECTIONS:
            with self.subTest(section=section):
                self.assertIn(section, body)

    def test_verbatim_rollback_mitigation(self) -> None:
        body = KNOWLEDGE_DOC.read_text()
        self.assertIn(self.VERBATIM_MITIGATION, body)

    def test_line_count_50_to_120(self) -> None:
        lines = KNOWLEDGE_DOC.read_text().splitlines()
        self.assertGreaterEqual(len(lines), 50)
        self.assertLessEqual(len(lines), 120)


if __name__ == "__main__":
    unittest.main()
