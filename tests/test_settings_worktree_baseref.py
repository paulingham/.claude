"""Slice A' AC3: settings.json declares worktree.baseRef = "fresh".

The `worktree.baseRef` top-level key pins the base reference that the
v2.1.140+ harness uses when materialising sub-agent worktrees. The
canonical value is `"fresh"` — multi-slice cherry-pick semantics that
preserve Iron Law 4 (REPO_ROOT HEAD stays on `main`).

Alternative considered: `"head"` couples each spawn's worktree to the
repo HEAD at spawn time, fighting both the cherry-pick chain and the
main-branch invariant. Rejected in plan.md § Alternatives Considered.
"""
import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SETTINGS_PATH = REPO_ROOT / "settings.json"


class WorktreeBlockExistsAndPinned(unittest.TestCase):
    def test_settings_worktree_baseref_is_fresh(self):
        data = json.loads(SETTINGS_PATH.read_text())
        self.assertIn(
            "worktree", data,
            "settings.json must declare a top-level `worktree` block"
        )
        worktree = data["worktree"]
        self.assertIsInstance(
            worktree, dict,
            f"worktree must be a JSON object, got {type(worktree).__name__}"
        )
        self.assertIn(
            "baseRef", worktree,
            "worktree must declare a `baseRef` key"
        )
        self.assertEqual(
            worktree["baseRef"], "fresh",
            f"worktree.baseRef must be the literal 'fresh' (multi-slice "
            f"cherry-pick semantics + Iron Law 4 alignment), got "
            f"{worktree['baseRef']!r}"
        )


if __name__ == "__main__":
    unittest.main()
