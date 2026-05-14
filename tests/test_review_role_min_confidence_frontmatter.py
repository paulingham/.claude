"""AC7 — review-role agents declare `min_confidence: 0.5` in frontmatter.

Set-equality check: EXACTLY {code-reviewer, security-engineer, patch-critic,
spec-blind-validator} declare `min_confidence:` and no other agent file does.
Value is the float 0.5 (not a quoted string).
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))

from agent_frontmatter_io import read_frontmatter  # noqa: E402

EXPECTED = {"code-reviewer", "security-engineer", "patch-critic",
            "spec-blind-validator"}


def _agents_declaring_min_confidence():
    declared = {}
    for path in sorted((REPO_ROOT / "agents").glob("*.md")):
        fm = read_frontmatter(path)
        if "min_confidence" in fm:
            declared[path.stem] = fm["min_confidence"]
    return declared


class ReviewRoleFrontmatter(unittest.TestCase):
    def test_exact_set_of_agents_declares_min_confidence(self):
        declared = _agents_declaring_min_confidence()
        self.assertEqual(set(declared.keys()), EXPECTED,
                         f"min_confidence declarers diverged from expected: "
                         f"{set(declared.keys())} vs {EXPECTED}")

    def test_min_confidence_value_is_05_float(self):
        declared = _agents_declaring_min_confidence()
        self.assertEqual(set(declared.keys()), EXPECTED,
                         "Cannot validate values until set-equality holds; "
                         "fix the set-equality test first")
        for name, value in declared.items():
            self.assertIsInstance(
                value, float,
                f"{name}.md min_confidence must be YAML float, got {type(value).__name__}")
            self.assertEqual(value, 0.5,
                             f"{name}.md min_confidence must be 0.5, got {value}")


if __name__ == "__main__":
    unittest.main()
