"""Tests for the floor_override kwarg on resolve_for_agent (slice-b AC5).

Contract:
- floor_override (when not None) WINS over env CLAUDE_INSTINCT_MIN_CONFIDENCE.
- floor_override=None preserves today's env->kwarg->default precedence.
- Anti-pattern +0.1 boost composes against the effective floor (override).
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hooks" / "_lib"))

from instinct_injector import resolve_for_agent  # noqa: E402


def _instinct(iid="i1", confidence=0.5, summary="P"):
    return {"id": iid, "confidence": confidence,
            "roles": ["software-engineer"], "domain": "general",
            "scope": "global", "pattern_summary": summary}


def _ap(iid, confidence, summary):
    return {**_instinct(iid=iid, confidence=confidence, summary=summary),
            "category": "anti-pattern"}


class FloorOverridePrecedence(unittest.TestCase):
    def test_floor_override_wins_over_env(self):
        i = _instinct(iid="mid", confidence=0.45, summary="mid-value")
        with patch.dict("os.environ", {"CLAUDE_INSTINCT_MIN_CONFIDENCE": "0.3"}):
            out = resolve_for_agent("any", ["software-engineer"], [i],
                                    floor_override=0.5)
        # 0.45 < override 0.5 -> filtered; env 0.3 must NOT win.
        self.assertNotIn("mid-value", out)

    def test_floor_override_none_preserves_env_precedence(self):
        i = _instinct(iid="lo", confidence=0.35, summary="kept-by-env")
        with patch.dict("os.environ", {"CLAUDE_INSTINCT_MIN_CONFIDENCE": "0.3"}):
            out = resolve_for_agent("any", ["software-engineer"], [i],
                                    floor_override=None)
        self.assertIn("kept-by-env", out)

    def test_anti_pattern_boost_composes_with_override_floor(self):
        # Override floor 0.5; boosted floor 0.6.
        # Positive at 0.55 -> dropped (below boosted floor).
        # Anti-pattern at 0.51 -> kept (immune to its own boost).
        positive = _instinct(iid="pos", confidence=0.55, summary="positive")
        ap = _ap("ap1", 0.51, "edge-case")
        out = resolve_for_agent("any", ["software-engineer"],
                                [positive, ap], floor_override=0.5)
        self.assertNotIn("positive", out)
        self.assertIn("AVOID: edge-case", out)


if __name__ == "__main__":
    unittest.main()
