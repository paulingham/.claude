"""Slice E AC-E3 — new instinct documents the pure-deny vs mutation-semantic
hook-enforcement split.

The schema-constraint knowledge previously lived only in inline hook
comments and plan.md prose (architect-context.md anti-finding). Promoting
it to a portable instinct lets future plan/architect work pick up the
split without re-deriving it from prose.
"""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INSTINCT = REPO_ROOT / "learning" / "instincts" / "hook-enforcement-semantics.md"


class HookEnforcementSemanticsInstinctExists(unittest.TestCase):
    def test_hook_enforcement_semantics_instinct_exists(self):
        self.assertTrue(INSTINCT.exists(),
                        f"expected instinct file at {INSTINCT}")
        body = INSTINCT.read_text()
        # Two named sections — pure-deny path is flippable, mutation
        # semantic depends on modified_tool_input round-trip
        self.assertIn("pure-deny", body)
        self.assertIn("mutation-semantic", body)


if __name__ == "__main__":
    unittest.main()
