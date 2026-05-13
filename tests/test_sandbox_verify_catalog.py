"""AC1 — verdict-catalog rows for the three SANDBOX verdicts.

Parses `rules/verdict-catalog.md` with the same regex
`tests/test_verdict_catalog_consistency.py` uses, asserts each of the
three new verdicts has the correct polarity, emitter (`sandbox-verify`),
phase (`build`), AND that the SANDBOX_SKIPPED branch column mentions the
`no-e2b-token` reason enum value (Story-1 scope).
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG = REPO_ROOT / "rules" / "verdict-catalog.md"


def _parse_catalog_rows():
    """Return list of dicts: {verdict, polarity, emitters, phase, branch}.

    Mirrors `tests/test_verdict_catalog_consistency.py:_parse_catalog_rows`.
    """
    rows = []
    body = CATALOG.read_text()
    pattern = re.compile(
        r"^\|\s*`([^`]+)`\s*\|\s*([a-z]+)\s*\|"
        r"\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*(.+?)\s*\|$",
        re.MULTILINE)
    for m in pattern.finditer(body):
        emitter_cell = m.group(3)
        emitters = [e.strip().strip("`")
                    for e in emitter_cell.split(",")
                    if e.strip().strip("`")]
        rows.append({
            "verdict": m.group(1),
            "polarity": m.group(2),
            "emitters": emitters,
            "phase": m.group(4).strip(),
            "branch": m.group(5).strip(),
        })
    return rows


class SandboxVerdictsPresentWithCorrectPolarityAndEmitter(unittest.TestCase):
    """Each of the three SANDBOX_* verdicts exists with the correct shape."""

    def setUp(self):
        rows = _parse_catalog_rows()
        self.by_verdict = {r["verdict"]: r for r in rows}

    def _assert_row(self, name, polarity):
        self.assertIn(name, self.by_verdict,
                      f"rules/verdict-catalog.md must contain a `{name}` row")
        row = self.by_verdict[name]
        self.assertEqual(row["polarity"], polarity,
                         f"{name} must have polarity={polarity}")
        self.assertIn("sandbox-verify", row["emitters"],
                      f"{name} emitter must be `sandbox-verify`")
        self.assertEqual(row["phase"], "build",
                         f"{name} phase must be `build`")
        return row

    def test_sandbox_verdicts_present_with_correct_polarity_and_emitter(self):
        self._assert_row("SANDBOX_VERIFIED", "success")
        self._assert_row("SANDBOX_FAILED", "failure")
        skipped = self._assert_row("SANDBOX_SKIPPED", "info")
        self.assertIn(
            "no-e2b-token", skipped["branch"],
            "SANDBOX_SKIPPED branch column must enumerate `no-e2b-token` reason")


class SandboxSkippedBranchEnumeratesStory2Reasons(unittest.TestCase):
    """AC3 + AC4 — SANDBOX_SKIPPED catalog row enumerates the two
    Story-2 reasons inline (`no-testable-changes`, `env-hatch`).

    Story 1 shipped the row with `no-e2b-token` only. Story 2 extends to
    `reason ∈ {no-e2b-token, no-testable-changes, env-hatch}` so a Story-3
    enum extension is caught by the lockstep test below.
    """

    def setUp(self):
        rows = _parse_catalog_rows()
        by_verdict = {r["verdict"]: r for r in rows}
        self.assertIn(
            "SANDBOX_SKIPPED", by_verdict,
            "rules/verdict-catalog.md must contain a `SANDBOX_SKIPPED` row")
        self.skipped_branch = by_verdict["SANDBOX_SKIPPED"]["branch"]

    def test_ac3_sandbox_skipped_branch_enumerates_no_testable_changes(self):
        self.assertIn(
            "no-testable-changes", self.skipped_branch,
            "SANDBOX_SKIPPED branch column must enumerate "
            "`no-testable-changes` reason (AC3 — docs-only path)")

    def test_ac4_sandbox_skipped_branch_enumerates_env_hatch(self):
        self.assertIn(
            "env-hatch", self.skipped_branch,
            "SANDBOX_SKIPPED branch column must enumerate "
            "`env-hatch` reason (AC4 — CLAUDE_DISABLE_SANDBOX_VERIFY=1)")


class SandboxSkippedReasonsLockstepWithSkillBody(unittest.TestCase):
    """Contract — the SANDBOX_SKIPPED reason enum in
    `rules/verdict-catalog.md` MUST be a subset of the reasons documented
    in `skills/build-implementation/SKILL.md` Step 5b body (so any Story-3
    enum extension that updates the catalog row but forgets the SKILL.md
    text — or vice versa — fails CI).

    Today (Story 2): the catalog row enumerates three reasons exactly:
    `no-e2b-token`, `no-testable-changes`, `env-hatch`. Every catalog
    reason MUST also appear in Step 5b body (the source-of-truth doc).
    Reasons that appear in Step 5b but not yet in the catalog are
    permitted — Story 3 will close the gap when it lands `no-e2b-token`
    in skill body and adds new reasons to the catalog.
    """

    REPO_ROOT = Path(__file__).resolve().parents[1]
    CATALOG = REPO_ROOT / "rules" / "verdict-catalog.md"
    SKILL = (REPO_ROOT / "skills" / "build-implementation"
             / "SKILL.md")

    # Canonical SKILL.md-side reason tokens that Story-2 lands inline.
    # Story 3 will extend Step 5b body with `no-e2b-token` (and add new
    # reasons to the catalog). Lockstep is one-directional today: every
    # CATALOG reason must appear in SKILL.md; the reverse is not required
    # until Story 3 lands.
    KNOWN_CATALOG_REASONS = (
        "no-e2b-token",
        "no-testable-changes",
        "env-hatch",
    )

    def setUp(self):
        rows = _parse_catalog_rows()
        by_verdict = {r["verdict"]: r for r in rows}
        self.skipped_branch = by_verdict["SANDBOX_SKIPPED"]["branch"]
        self.skill_text = self.SKILL.read_text()

    def test_sandbox_skipped_reasons_lockstep_with_skill_body(self):
        # Every reason the catalog enumerates MUST also be documented in
        # the SKILL.md prose (single source of truth for skip-reason
        # semantics). Story 3's `no-e2b-token` skill addition closes the
        # remaining one-directional gap; for now we only assert the two
        # Story-2 reasons exist in skill prose.
        for story2_reason in ("no-testable-changes", "env-hatch"):
            self.assertIn(
                story2_reason, self.skipped_branch,
                f"CATALOG: SANDBOX_SKIPPED branch must enumerate "
                f"`{story2_reason}` reason")
            self.assertIn(
                story2_reason, self.skill_text,
                f"SKILL.md: Step 5b body must document `{story2_reason}` "
                f"skip reason in lockstep with the catalog row")


if __name__ == "__main__":
    unittest.main()
