"""Gap 2 — /pr-creation skill misfire regression guards.

Investigation surfaced two structural differences between this skill and
peers that auto-invoke reliably (internal-eval, learn, build-implementation,
code-review, security-review, verify, product-acceptance, patch-critique):

1. Every working skill's `description` field starts with `"Use when user
   wants to ..."` or `"Use when user wants ..."`. The pre-fix pr-creation
   description started with `"GitHub pull request workflow ..."` — no
   action cue for the model-invocation router.
2. Every working skill has a `## Known Misfire Mode` escape hatch is now
   documented in pr-creation so operators investigating recurrences have
   a workaround.

These tests pin both invariants. If the misfire recurs after future skill
edits, the test failures point straight at the regressed property.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "pr-creation" / "SKILL.md"


def _frontmatter():
    body = SKILL.read_text()
    match = re.match(r"^---\n(.*?)\n---", body, re.DOTALL)
    assert match, "pr-creation SKILL.md missing YAML frontmatter"
    return match.group(1)


class PrCreationDescriptionStartsWithUseWhen(unittest.TestCase):
    """Pin the model-invocation cue prefix."""

    def test_description_starts_with_use_when_user_wants_to(self):
        fm = _frontmatter()
        match = re.search(r'^description:\s*"([^"]+)"', fm, re.MULTILINE)
        self.assertIsNotNone(
            match, "description field missing or not quoted")
        description = match.group(1)
        self.assertTrue(
            description.startswith("Use when user wants to ")
            or description.startswith("Use when user wants "),
            msg=(
                f"description must start with the model-invocation cue "
                f'"Use when user wants to ...". Got: {description!r}'
            ),
        )


class PrCreationDocumentsKnownMisfireMode(unittest.TestCase):
    """Pin the documented workaround so future skill edits cannot drop it
    until the root cause is proven and the misfire is closed."""

    def test_skill_body_has_known_misfire_mode_section(self):
        body = SKILL.read_text()
        self.assertIn(
            "## Known Misfire Mode", body,
            msg=(
                "skills/pr-creation/SKILL.md must document the Story-2 "
                "misfire mode until the root cause is proven."
            ),
        )

    def test_misfire_section_names_workaround(self):
        body = SKILL.read_text()
        self.assertRegex(
            body,
            r"(?i)workaround",
            msg="misfire section must describe a workaround",
        )

    def test_misfire_section_points_at_internal_eval_for_comparison(self):
        """Action note must point operators at a known-working skill."""
        body = SKILL.read_text()
        self.assertIn(
            "internal-eval", body,
            msg=(
                "misfire section must reference internal-eval (or another "
                "known-working skill) as a comparison target."
            ),
        )


class PrCreationStep2InvokesHookPytestGate(unittest.TestCase):
    """Pin that Step 2 wires the hook-change pytest gate before any gh call.

    The gate is bypass-proof vs `gh api` because it is a SKILL STEP, not a
    gh-keyed PreToolUse hook. This test locks the call-site so this invariant
    cannot silently regress (GP-19 closure, AC5).
    """

    def _step2_block(self) -> str:
        """Extract the Step 2 block from SKILL.md body."""
        body = SKILL.read_text()
        match = re.search(
            r"(### 2\. Run Pre-Push Validation.*?)(?=\n### [0-9]+\.|\Z)",
            body,
            re.DOTALL,
        )
        self.assertIsNotNone(
            match,
            "Could not find '### 2. Run Pre-Push Validation' block in SKILL.md",
        )
        return match.group(1)

    def test_pr_creation_step2_invokes_hook_pytest_gate(self):
        """Step 2 must name check-hook-pytest-gate.sh before the gh pr create example."""
        block = self._step2_block()

        gate_pos = block.find("check-hook-pytest-gate.sh")
        self.assertGreater(
            gate_pos,
            -1,
            msg=(
                "skills/pr-creation/SKILL.md Step 2 must invoke "
                "'check-hook-pytest-gate.sh' before any 'gh pr create' call. "
                "This pins the GP-19 bypass-proof call-site (AC5)."
            ),
        )

        gh_pos = block.find("gh pr create")
        if gh_pos != -1:
            self.assertLess(
                gate_pos,
                gh_pos,
                msg=(
                    "check-hook-pytest-gate.sh must appear BEFORE 'gh pr create' "
                    "in Step 2 of SKILL.md."
                ),
            )


if __name__ == "__main__":
    unittest.main()
