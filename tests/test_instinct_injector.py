"""Unit tests for hooks/_lib/instinct_injector.py (Wave 4-M Slice 1)."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hooks" / "_lib"))

from instinct_injector import resolve_for_agent  # noqa: E402


def _instinct(
    iid="i1", confidence=0.5, roles=None, domain="general",
    scope="global", pattern_summary="Default summary",
):
    return {
        "id": iid,
        "confidence": confidence,
        "roles": list(roles) if roles is not None else ["software-engineer"],
        "domain": domain,
        "scope": scope,
        "pattern_summary": pattern_summary,
    }


class FilterByRole(unittest.TestCase):
    def test_filter_by_role_intersects(self):
        instincts = [_instinct(roles=["a", "b"])]
        out = resolve_for_agent("any", ["b", "c"], instincts)
        self.assertIn("Default summary", out)

    def test_filter_by_role_no_intersection(self):
        instincts = [_instinct(roles=["a"])]
        out = resolve_for_agent("any", ["b", "c"], instincts)
        self.assertEqual(out, "")

    def test_filter_by_role_empty_categories(self):
        instincts = [_instinct(roles=["a"])]
        self.assertEqual(resolve_for_agent("any", [], instincts), "")


class FilterByConfidence(unittest.TestCase):
    def test_filter_by_confidence_floor(self):
        below = _instinct(iid="lo", confidence=0.39)
        above = _instinct(iid="hi", confidence=0.40, pattern_summary="kept")
        out = resolve_for_agent("any", ["software-engineer"], [below, above])
        self.assertIn("kept", out)
        self.assertNotIn("Default summary", out)


def _make_n(count, confidence=0.9):
    return [
        _instinct(iid=f"i{n:02d}", confidence=confidence, pattern_summary=f"P{n:02d}")
        for n in range(count)
    ]


class TopNCap(unittest.TestCase):
    def test_top_n_caps_at_5_default(self):
        out = resolve_for_agent("any", ["software-engineer"], _make_n(7))
        bullets = [ln for ln in out.splitlines() if ln.startswith("-")]
        self.assertEqual(len(bullets), 5)

    def test_top_n_env_override_zero(self):
        with patch.dict("os.environ", {"CLAUDE_INSTINCT_TOP_N": "0"}):
            out = resolve_for_agent("any", ["software-engineer"], _make_n(3))
        self.assertEqual(out, "")

    def test_top_n_env_override_high(self):
        with patch.dict("os.environ", {"CLAUDE_INSTINCT_TOP_N": "100"}):
            out = resolve_for_agent("any", ["software-engineer"], _make_n(7))
        bullets = [ln for ln in out.splitlines() if ln.startswith("-")]
        self.assertEqual(len(bullets), 7)

    def test_top_n_env_override_invalid(self):
        with patch.dict("os.environ", {"CLAUDE_INSTINCT_TOP_N": "abc"}):
            out = resolve_for_agent("any", ["software-engineer"], _make_n(7))
        bullets = [ln for ln in out.splitlines() if ln.startswith("-")]
        self.assertEqual(len(bullets), 5)


class MinConfidenceEnv(unittest.TestCase):
    def test_min_confidence_env_override(self):
        low = _instinct(iid="lo", confidence=0.05, pattern_summary="low-conf")
        with patch.dict("os.environ", {"CLAUDE_INSTINCT_MIN_CONFIDENCE": "0.0"}):
            out = resolve_for_agent("any", ["software-engineer"], [low])
        self.assertIn("low-conf", out)


class Dedup(unittest.TestCase):
    def test_dedup_by_id_keeps_highest_confidence(self):
        lo = _instinct(iid="dup", confidence=0.5, pattern_summary="lo")
        hi = _instinct(iid="dup", confidence=0.7, pattern_summary="hi")
        out = resolve_for_agent("any", ["software-engineer"], [lo, hi])
        self.assertIn("hi", out)
        self.assertNotIn("lo (general)", out)

    def test_dedup_cross_scope_project_wins(self):
        glob = _instinct(iid="dup", confidence=0.5, scope="global",
                         pattern_summary="from-global")
        proj = _instinct(iid="dup", confidence=0.5, scope="project",
                         pattern_summary="from-project")
        out = resolve_for_agent("any", ["software-engineer"], [glob, proj])
        self.assertIn("from-project", out)
        self.assertNotIn("from-global", out)


class SortAndFormat(unittest.TestCase):
    def test_sort_descending_by_confidence(self):
        a = _instinct(iid="a", confidence=0.50, pattern_summary="C")
        b = _instinct(iid="b", confidence=0.95, pattern_summary="A")
        c = _instinct(iid="c", confidence=0.80, pattern_summary="B")
        out = resolve_for_agent("any", ["software-engineer"], [a, b, c])
        bullets = [ln for ln in out.splitlines() if ln.startswith("-")]
        self.assertEqual(bullets[0].split("]")[0], "- [0.95")
        self.assertEqual(bullets[1].split("]")[0], "- [0.80")
        self.assertEqual(bullets[2].split("]")[0], "- [0.50")

    def test_format_uses_pattern_summary_body(self):
        i = _instinct(iid="x", confidence=0.50, domain="security",
                      pattern_summary="Validate at boundary")
        out = resolve_for_agent("any", ["software-engineer"], [i])
        self.assertIn("- [0.50] Validate at boundary (security)", out)

    def test_format_truncates_long_summary_at_200(self):
        body = "x" * 250
        i = _instinct(iid="x", pattern_summary=body)
        out = resolve_for_agent("any", ["software-engineer"], [i])
        bullet = next(ln for ln in out.splitlines() if ln.startswith("-"))
        self.assertIn("x" * 200 + "...", bullet)
        self.assertNotIn("x" * 201, bullet)


class EmptyPaths(unittest.TestCase):
    def test_empty_input_returns_empty_string(self):
        self.assertEqual(resolve_for_agent("any", ["software-engineer"], []), "")

    def test_empty_after_filter_returns_empty_string(self):
        i = _instinct(roles=["nobody"])
        self.assertEqual(resolve_for_agent("any", ["software-engineer"], [i]), "")


class RegressionContract(unittest.TestCase):
    def test_returns_list_not_string_for_roles_field(self):
        valid = _instinct(roles=["a", "b"], pattern_summary="ok")
        out = resolve_for_agent("any", ["a"], [valid])
        self.assertIn("ok", out)
        broken = dict(valid)
        broken["roles"] = "[a, b]"
        with self.assertRaises(TypeError):
            resolve_for_agent("any", ["a"], [broken])


class SecondarySortStability(unittest.TestCase):
    def test_secondary_sort_by_id_ascending_on_confidence_tie(self):
        zzz = _instinct(iid="zzz", confidence=0.85, pattern_summary="from-zzz")
        aaa = _instinct(iid="aaa", confidence=0.85, pattern_summary="from-aaa")
        out = resolve_for_agent("any", ["software-engineer"], [zzz, aaa])
        bullets = [ln for ln in out.splitlines() if ln.startswith("-")]
        self.assertIn("from-aaa", bullets[0])
        self.assertIn("from-zzz", bullets[1])


# ---------------- C8 S3: anti-pattern +0.1 floor boost ---------------------


def _ap(iid, confidence, summary):
    """Anti-pattern instinct with the C8 `category` field set."""
    return {**_instinct(iid=iid, confidence=confidence, pattern_summary=summary),
            "category": "anti-pattern"}


class AntiPatternFloorBoost(unittest.TestCase):
    """When at least one anti-pattern survives the base filters, the floor
    is boosted by +0.1 for non-anti-pattern instincts. Anti-patterns
    themselves are immune to the boost they trigger.
    """

    def test_weak_positive_dropped_when_antipattern_present(self):
        weak = _instinct(iid="weak", confidence=0.45, pattern_summary="weak")
        ap = _ap("ap1", 0.55, "danger")
        out = resolve_for_agent("any", ["software-engineer"], [weak, ap],
                                min_confidence=0.4)
        # Boosted floor is 0.5 — `weak` (0.45) drops; `ap` (0.55) survives.
        self.assertNotIn("weak", out)
        self.assertIn("AVOID: danger", out)

    def test_antipattern_survives_when_its_confidence_below_boosted_floor(self):
        # Anti-patterns must survive the boost they trigger. Base 0.5 +
        # boost = 0.6; the anti-pattern at 0.51 would be evicted by a
        # naive re-filter, but C8 explicitly preserves it.
        ap = _ap("ap1", 0.51, "edge-case")
        out = resolve_for_agent("any", ["software-engineer"], [ap],
                                min_confidence=0.5)
        self.assertIn("AVOID: edge-case", out)

    def test_floor_unchanged_when_no_antipattern_selected(self):
        # Two positives both above base floor 0.4: both survive (boost
        # only fires when an anti-pattern is among the survivors).
        a = _instinct(iid="a", confidence=0.45, pattern_summary="alpha")
        b = _instinct(iid="b", confidence=0.55, pattern_summary="beta")
        out = resolve_for_agent("any", ["software-engineer"], [a, b],
                                min_confidence=0.4)
        self.assertIn("alpha", out)
        self.assertIn("beta", out)

    def test_env_min_confidence_05_plus_boost_yields_06_floor(self):
        # CLAUDE_INSTINCT_MIN_CONFIDENCE=0.5 + anti-pattern present →
        # effective floor 0.6 for non-anti-patterns.
        weak = _instinct(iid="weak", confidence=0.55, pattern_summary="below")
        strong = _instinct(iid="strong", confidence=0.65,
                           pattern_summary="above")
        ap = _ap("ap1", 0.7, "trigger")
        with patch.dict("os.environ",
                        {"CLAUDE_INSTINCT_MIN_CONFIDENCE": "0.5"}):
            out = resolve_for_agent("any", ["software-engineer"],
                                    [weak, strong, ap])
        self.assertNotIn("below", out)  # 0.55 < boosted floor 0.6
        self.assertIn("above", out)     # 0.65 >= 0.6
        self.assertIn("AVOID: trigger", out)


class AntiPatternFloorBoostMultipleAntiPatterns(unittest.TestCase):
    """Risk-Register regression: when N>1 anti-patterns survive the
    base filters, every anti-pattern must remain in the survivor set
    (the boost-preserve clause must not drop any of them) AND the
    +0.1 boost must still be applied exactly once to non-anti-pattern
    confidence.
    """

    def test_two_anti_patterns_both_survive_and_weak_positive_drops(self):
        # Two anti-patterns at 0.50 and 0.55 — both BELOW the boosted
        # floor of 0.5 (base 0.4 + 0.1). They must both survive via
        # the self-immunity clause. The weak positive at 0.45 must
        # drop.
        ap1 = _ap("ap1", 0.50, "first-danger")
        ap2 = _ap("ap2", 0.55, "second-danger")
        weak = _instinct(iid="weak", confidence=0.45,
                         pattern_summary="weak-positive")
        out = resolve_for_agent("any", ["software-engineer"],
                                [ap1, ap2, weak], min_confidence=0.4)
        self.assertIn("AVOID: first-danger", out)
        self.assertIn("AVOID: second-danger", out)
        self.assertNotIn("weak-positive", out)

    def test_three_anti_patterns_all_survive_under_boosted_floor(self):
        # Three anti-patterns all under the boosted floor — confirms
        # the self-immunity clause is `or`, not exclusive of multiples.
        ap1 = _ap("ap1", 0.51, "alpha-avoid")
        ap2 = _ap("ap2", 0.52, "beta-avoid")
        ap3 = _ap("ap3", 0.53, "gamma-avoid")
        out = resolve_for_agent("any", ["software-engineer"],
                                [ap1, ap2, ap3], min_confidence=0.5)
        # Boosted floor would be 0.6; all three at 0.51-0.53 survive
        # only because anti-patterns are immune to their own boost.
        self.assertIn("AVOID: alpha-avoid", out)
        self.assertIn("AVOID: beta-avoid", out)
        self.assertIn("AVOID: gamma-avoid", out)


if __name__ == "__main__":
    unittest.main()
