"""Tests for the Decision Ladder preamble in build agent files — RED-first TDD.

AC1  7 rungs present (in order) in BOTH agent files; ladder heading within ~a few
     lines of "Rationalization Red Flags" in both; "after you understand the
     problem" framing present in both.
AC2  all 5 carve-outs present in both; carve-outs byte-identical across agents;
     carve-outs marked "NEVER simplified away".
AC3  SKILL.md has the ladder note; note sits after "IMPLEMENT CLEANLY" and before
     "### Step 3" (both unique strings).
AC4  all three files mark the ladder advisory/"gates nothing"; the SKILL note does
     NOT contain cap-literals (">5 lines" / ">12 lines"); no new blocking hook
     matcher introduced in hooks.json or settings.json.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

SE_MD = REPO_ROOT / "agents" / "software-engineer.md"
FE_MD = REPO_ROOT / "agents" / "frontend-engineer.md"
SKILL_MD = REPO_ROOT / "skills" / "build-implementation" / "SKILL.md"
HOOKS_JSON = REPO_ROOT / "hooks" / "hooks.json"
SETTINGS_JSON = REPO_ROOT / ".claude" / "settings.json"

RUNGS = [
    "Does this need to exist at all? (YAGNI)",
    "Is it already in this codebase? Reuse it.",
    "Does the standard library do it?",
    "Is there a native platform feature for it?",
    "Does an already-installed dependency cover it?",
    "Can it be one line?",
    "Only then: write the minimum that works.",
]

CARVEOUTS = [
    "trust-boundary / input validation",
    "error handling that prevents data loss or silent correctness failures",
    "security",
    "accessibility",
    "explicitly-requested features",
]

_CARVEOUT_SENTINEL = "NEVER simplified away"


def _extract_carveout_block(text: str) -> str:
    """Extract the carve-out block from sentinel to the next markdown heading."""
    start = text.find(_CARVEOUT_SENTINEL)
    if start == -1:
        return ""
    end = text.find("\n## ", start)
    if end == -1:
        end = len(text)
    return text[start:end].strip()


# ──────────────────────────────────────────────────────────────
# AC1: Ladder present, anchored, framed
# ──────────────────────────────────────────────────────────────

class AC1LadderPresentAnchoredFramed(unittest.TestCase):

    def _assert_has_all_seven_rungs(self, path: Path) -> None:
        text = path.read_text()
        for rung in RUNGS:
            self.assertIn(
                rung, text,
                f"{path.name} must contain rung: {rung!r}",
            )

    def _assert_rungs_in_order(self, path: Path) -> None:
        text = path.read_text()
        positions = [text.find(r) for r in RUNGS]
        self.assertNotIn(-1, positions, f"{path.name}: not all rungs found")
        self.assertEqual(
            positions, sorted(positions),
            f"{path.name}: rungs must appear in order 1-7",
        )

    def test_software_engineer_has_seven_rungs(self):
        self._assert_has_all_seven_rungs(SE_MD)

    def test_frontend_engineer_has_seven_rungs(self):
        self._assert_has_all_seven_rungs(FE_MD)

    def _assert_ladder_anchored_near_red_flags(self, path: Path) -> None:
        text = path.read_text()
        red_flags_pos = text.find("Rationalization Red Flags")
        self.assertNotEqual(red_flags_pos, -1,
                            f"{path.name}: 'Rationalization Red Flags' heading not found")
        ladder_pos = text.find("Decision Ladder")
        self.assertNotEqual(ladder_pos, -1,
                            f"{path.name}: 'Decision Ladder' heading not found")
        # The ladder heading must come after Red Flags and within ~40 lines
        between = text[red_flags_pos:ladder_pos]
        line_gap = between.count("\n")
        self.assertGreater(ladder_pos, red_flags_pos,
                           f"{path.name}: ladder must appear after Red Flags")
        self.assertLessEqual(line_gap, 40,
                             f"{path.name}: ladder must be within ~40 lines of Red Flags")

    def test_ladder_anchored_near_red_flags_software(self):
        self._assert_ladder_anchored_near_red_flags(SE_MD)

    def test_ladder_anchored_near_red_flags_frontend(self):
        self._assert_ladder_anchored_near_red_flags(FE_MD)

    def test_ladder_framed_after_comprehension(self):
        phrase = "after you understand the problem"
        for path in (SE_MD, FE_MD):
            text = path.read_text()
            self.assertIn(phrase, text,
                          f"{path.name}: must contain framing phrase {phrase!r}")


# ──────────────────────────────────────────────────────────────
# AC2: Carve-outs present, verbatim, byte-identical across agents
# ──────────────────────────────────────────────────────────────

class AC2CarvoutsPresent(unittest.TestCase):

    def _assert_all_carveouts(self, path: Path) -> None:
        text = path.read_text()
        for carveout in CARVEOUTS:
            self.assertIn(
                carveout, text,
                f"{path.name} must contain carve-out: {carveout!r}",
            )

    def test_software_engineer_has_all_five_carveouts(self):
        self._assert_all_carveouts(SE_MD)

    def test_frontend_engineer_has_all_five_carveouts(self):
        self._assert_all_carveouts(FE_MD)

    def test_carveouts_are_verbatim_identical_across_agents(self):
        se_block = _extract_carveout_block(SE_MD.read_text())
        fe_block = _extract_carveout_block(FE_MD.read_text())
        self.assertNotEqual(se_block, "",
                            "software-engineer.md: carve-out block not found")
        self.assertNotEqual(fe_block, "",
                            "frontend-engineer.md: carve-out block not found")
        self.assertEqual(
            se_block, fe_block,
            "Carve-out blocks must be byte-identical across agent files",
        )

    def test_carveouts_marked_never_simplified(self):
        for path in (SE_MD, FE_MD):
            text = path.read_text()
            self.assertIn(
                _CARVEOUT_SENTINEL, text,
                f"{path.name}: carve-outs must be marked {_CARVEOUT_SENTINEL!r}",
            )


# ──────────────────────────────────────────────────────────────
# AC3: SKILL.md ladder note anchored between IMPLEMENT and Step 3
# ──────────────────────────────────────────────────────────────

class AC3SkillNoteAnchored(unittest.TestCase):

    def test_skill_has_decision_ladder_note(self):
        text = SKILL_MD.read_text()
        self.assertIn(
            "decision ladder", text.lower(),
            "build-implementation SKILL.md must contain a decision ladder note",
        )

    def test_skill_note_sits_between_implement_and_shape(self):
        text = SKILL_MD.read_text()
        implement_pos = text.find("IMPLEMENT CLEANLY")
        step3_pos = text.find("### Step 3")
        ladder_pos = text.lower().find("decision ladder")
        self.assertNotEqual(implement_pos, -1,
                            "SKILL.md must contain 'IMPLEMENT CLEANLY'")
        self.assertNotEqual(step3_pos, -1,
                            "SKILL.md must contain '### Step 3'")
        self.assertNotEqual(ladder_pos, -1,
                            "SKILL.md must contain 'decision ladder' note")
        self.assertGreater(
            ladder_pos, implement_pos,
            "decision ladder note must come after 'IMPLEMENT CLEANLY'",
        )
        self.assertLess(
            ladder_pos, step3_pos,
            "decision ladder note must come before '### Step 3'",
        )


# ──────────────────────────────────────────────────────────────
# AC4: Advisory framing, no cap literals in SKILL note, no new hook
# ──────────────────────────────────────────────────────────────

class AC4AdvisoryAndNoHook(unittest.TestCase):

    def test_ladder_framed_advisory_in_all_three(self):
        for path in (SE_MD, FE_MD, SKILL_MD):
            text = path.read_text()
            self.assertRegex(
                text.lower(),
                r"advisory|gates nothing",
                f"{path.name}: ladder must be framed as advisory / 'gates nothing'",
            )

    def test_skill_cross_references_core_not_restate(self):
        text = SKILL_MD.read_text()
        # The ladder note must cross-reference rules/core.md
        self.assertIn(
            "rules/core.md", text,
            "SKILL.md ladder note must cross-reference rules/core.md",
        )
        # Find the ladder note region (between "decision ladder" and next heading)
        start = text.lower().find("decision ladder")
        end = text.find("\n###", start + 1)
        if end == -1:
            end = text.find("\n##", start + 1)
        if end == -1:
            end = len(text)
        note_region = text[start:end]
        # Cap literals must NOT appear in the note region
        self.assertNotIn(
            ">5 lines", note_region,
            "SKILL.md ladder note must NOT restate '>5 lines' cap literal",
        )
        self.assertNotIn(
            ">12 lines", note_region,
            "SKILL.md ladder note must NOT restate '>12 lines' cap literal",
        )

    def test_no_new_blocking_hook_introduced(self):
        """Neither hooks.json nor settings.json should gain a decision-ladder matcher."""
        for path in (HOOKS_JSON, SETTINGS_JSON):
            if not path.exists():
                continue
            text = path.read_text()
            self.assertNotIn(
                "decision-ladder", text,
                f"{path.name} must NOT contain a 'decision-ladder' hook matcher",
            )
            self.assertNotIn(
                "decision_ladder", text,
                f"{path.name} must NOT contain a 'decision_ladder' hook matcher",
            )


if __name__ == "__main__":
    unittest.main()
