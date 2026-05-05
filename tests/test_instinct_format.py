"""C8 S2: anti-pattern bullet rendering.

The renderer in `hooks/_lib/instinct_format.py` adds an `AVOID: ` prefix to
every instinct whose `category` is `"anti-pattern"`. The prefix sits
OUTSIDE the 200-char truncation budget — anti-pattern bullets may be up to
about 210 visible characters. Non-anti-pattern bullets (and legacy
instincts that predate the `category` field) render unchanged.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hooks" / "_lib"))

from instinct_format import render  # noqa: E402


def _instinct(category=None, confidence=0.7, summary="foo", domain="x"):
    out = {"confidence": confidence, "pattern_summary": summary,
           "domain": domain}
    if category is not None:
        out["category"] = category
    return out


class RenderAntiPatternBulletPrefix(unittest.TestCase):
    def test_anti_pattern_bullet_starts_with_avoid(self):
        out = render([_instinct(category="anti-pattern", confidence=0.7,
                                summary="foo", domain="x")])
        self.assertIn("- [0.70] AVOID: foo (x)", out)


class RenderNonAntiPatternBulletNoPrefix(unittest.TestCase):
    def test_pattern_category_does_not_get_avoid_prefix(self):
        out = render([_instinct(category="pattern", confidence=0.7,
                                summary="bar", domain="y")])
        self.assertNotIn("AVOID:", out)
        self.assertIn("- [0.70] bar (y)", out)


class RenderMissingCategoryNoPrefix(unittest.TestCase):
    def test_legacy_no_category_field_no_avoid_prefix(self):
        # Legacy instincts predate the `category` field — they must
        # render exactly as before.
        legacy = {"confidence": 0.5, "pattern_summary": "old", "domain": "z"}
        out = render([legacy])
        self.assertNotIn("AVOID:", out)
        self.assertIn("- [0.50] old (z)", out)


class RenderAntiPatternRespectsTruncationCap(unittest.TestCase):
    def test_avoid_prefix_does_not_push_total_length_past_truncation_target(
            self):
        # Given a 250-char `pattern_summary` and `category="anti-pattern"`:
        # the bullet body starts with "AVOID: " AND the substring AFTER
        # "AVOID: " is the 200-char truncated form (with "..." suffix).
        long_summary = "x" * 250
        out = render([_instinct(category="anti-pattern", confidence=0.7,
                                summary=long_summary, domain="z")])
        bullet = next(ln for ln in out.splitlines() if ln.startswith("-"))
        # Prefix is added AFTER truncation — outside the 200-char budget.
        self.assertIn("AVOID: ", bullet)
        # The truncated body (200 chars + "...") follows the prefix.
        truncated = "x" * 200 + "..."
        self.assertIn(f"AVOID: {truncated}", bullet)
        # And the un-truncated 201st `x` is NOT in the bullet.
        self.assertNotIn("x" * 201, bullet)


if __name__ == "__main__":
    unittest.main()
