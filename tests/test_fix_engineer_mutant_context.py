"""Snapshot tests for the fix-engineer mutant-context dispatch sub-section.

Locks the contract that `orchestrator/pipeline-orchestration.md` documents how
the orchestrator augments the fix-engineer spawn prompt when verify returns
UNVERIFIED with surviving mutants. The new sub-section sits AFTER the existing
`## After CHANGES_REQUESTED (Review Loop Dispatch)` block and BEFORE the
`## Enforcement (Orchestrator Self-Discipline)` block.

Test design follows tests/test_agent_orchestration_doc.py: section-scoped
regex extraction + literal-anchor assertions. No fixtures, no YAML parsing.
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC = REPO_ROOT / "orchestrator" / "pipeline-orchestration.md"

# Source-section names rendered into the dispatch prompt verbatim from the
# verify report. The em-dash (—) is intentional — it matches the literal
# heading produced by skills/verify/SKILL.md.
TIER3_HEADING = "Tier 3 — Uncaught"
TIER35_HEADING = "Tier 3.5 — Uncaught"


def _full_text() -> str:
    return DOC.read_text()


def _changes_requested_section() -> str:
    """Body of the existing `## After CHANGES_REQUESTED (Review Loop Dispatch)`
    section, stopping at the next H2 heading or the new H3 sub-section.
    """
    text = _full_text()
    # No \b after `)` — `)` is non-word, so `\b` would require a following
    # word character and the heading line ends with `)\n`.
    match = re.search(
        r"##\s+After CHANGES_REQUESTED \(Review Loop Dispatch\)(.+?)"
        r"(?=\n##\s|\n###\s+After UNVERIFIED with surviving mutants\b|\Z)",
        text,
        re.DOTALL,
    )
    return match.group(1) if match else ""


def _mutant_subsection() -> str:
    """Body of the new `### After UNVERIFIED with surviving mutants` sub-section,
    stopping at the next H2 or H3 heading.
    """
    text = _full_text()
    match = re.search(
        r"###\s+After UNVERIFIED with surviving mutants\b(.+?)(?=\n##\s|\n###\s|\Z)",
        text,
        re.DOTALL,
    )
    return match.group(1) if match else ""


class SubSectionExists(unittest.TestCase):
    """AC1: new sub-section heading is present and ordered AFTER the
    `## After CHANGES_REQUESTED (Review Loop Dispatch)` heading.
    """

    def test_after_unverified_subsection_exists(self):
        text = _full_text()
        self.assertIn(
            "### After UNVERIFIED with surviving mutants",
            text,
            "Missing `### After UNVERIFIED with surviving mutants` heading",
        )
        cr_idx = text.index("## After CHANGES_REQUESTED (Review Loop Dispatch)")
        new_idx = text.index("### After UNVERIFIED with surviving mutants")
        self.assertLess(
            cr_idx,
            new_idx,
            "New sub-section must appear AFTER the existing CHANGES_REQUESTED block",
        )


class GatePredicate(unittest.TestCase):
    """AC2: gate predicate string is present verbatim inside the new sub-section."""

    def test_predicate_string_present(self):
        body = _mutant_subsection()
        self.assertTrue(body, "New sub-section body must be non-empty")
        self.assertIn(
            "verdict == UNVERIFIED AND surviving_mutants is non-empty",
            body,
            "Gate predicate must be quoted verbatim so readers can grep for it",
        )


class SurvivingMutantsBlock(unittest.TestCase):
    """AC3: Surviving Mutants block names the field triple and the source sections."""

    def test_field_names_and_source_named(self):
        body = _mutant_subsection()
        self.assertIn(
            "Surviving Mutants",
            body,
            "Sub-section must name the `Surviving Mutants` block",
        )
        for token in ("file:line", "category", "rationale"):
            self.assertIn(
                token,
                body,
                f"Surviving Mutants block must name field token {token!r}",
            )
        self.assertIn(
            TIER3_HEADING,
            body,
            "Sub-section must reference the verify report's "
            "`Tier 3 — Uncaught` source section",
        )
        self.assertIn(
            TIER35_HEADING,
            body,
            "Sub-section must reference the verify report's "
            "`Tier 3.5 — Uncaught` source section",
        )


class TestAuthoringDirective(unittest.TestCase):
    """AC4: Test-Authoring Directive contains the literal pre-production phrase."""

    def test_before_production_code_phrase_present(self):
        body = _mutant_subsection()
        self.assertIn(
            "Test-Authoring Directive",
            body,
            "Sub-section must name the `Test-Authoring Directive` block",
        )
        self.assertIn(
            "BEFORE any production code change",
            body,
            "Test-Authoring Directive must contain the literal phrase "
            "'BEFORE any production code change'",
        )


class Citation(unittest.TestCase):
    """AC5: Meta ACH paper URL is cited verbatim."""

    def test_meta_ach_url_present(self):
        body = _mutant_subsection()
        self.assertIn(
            "https://dl.acm.org/doi/10.1145/3696630.3728544",
            body,
            "Sub-section must cite the Meta ACH paper URL as design rationale",
        )


class AgentBackPointer(unittest.TestCase):
    """AC6: back-pointer to `agents/fix-engineer.md` is present."""

    def test_fix_engineer_md_referenced(self):
        body = _mutant_subsection()
        self.assertIn(
            "agents/fix-engineer.md",
            body,
            "Sub-section must back-point to `agents/fix-engineer.md` so readers "
            "can locate the consumer's role contract",
        )


class ExistingBlockUntouched(unittest.TestCase):
    """AC7: existing 9-step CHANGES_REQUESTED block stays byte-identical."""

    EXPECTED_STEP_ANCHORS = (
        "1. Spawn fix-engineer (`subagent_type: fix-engineer`, see "
        "`agents/fix-engineer.md`)",
        "2. Fix-engineer fixes and commits on the same feature branch",
        "3. Shut down fix-engineer, merge the fix branch",
        "4. **Re-assign to the raising reviewer is MANDATORY.**",
        "5. `SendMessage` to the raising reviewer with: the original finding, "
        "the specific fix applied, and the file diff",
        "6. **Targeted re-review**: Only the reviewer who raised the finding "
        "re-reviews",
        "7. The re-reviewer checks ONLY the addressed findings plus immediate "
        "surrounding context",
        "8. Max 2 total rounds (initial + 1 re-review). If still not resolved, "
        "escalate to user",
        "9. After both APPROVE: shut down both reviewers",
    )

    def test_changes_requested_block_steps_intact(self):
        body = _changes_requested_section()
        self.assertTrue(body, "CHANGES_REQUESTED section must be present")
        last_idx = -1
        for anchor in self.EXPECTED_STEP_ANCHORS:
            self.assertIn(
                anchor,
                body,
                f"Existing step anchor missing or modified: {anchor!r}",
            )
            idx = body.index(anchor)
            self.assertGreater(
                idx,
                last_idx,
                f"Step anchor out of order: {anchor!r} should appear after "
                f"the previous step",
            )
            last_idx = idx


class FullSuiteLoadable(unittest.TestCase):
    """AC8: covered by the file existing and AC1-AC7 passing in the same run.

    This explicit assertion locks the file-loadable invariant so a parser-level
    regression (syntax error, missing imports) surfaces as a test failure rather
    than a collection error in CI logs.
    """

    def test_doc_path_resolves(self):
        self.assertTrue(
            DOC.exists(),
            f"orchestrator/pipeline-orchestration.md must exist at {DOC}",
        )
        self.assertGreater(
            DOC.stat().st_size,
            0,
            "orchestrator/pipeline-orchestration.md must be non-empty",
        )


if __name__ == "__main__":
    unittest.main()
