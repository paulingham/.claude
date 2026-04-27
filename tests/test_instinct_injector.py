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


if __name__ == "__main__":
    unittest.main()
