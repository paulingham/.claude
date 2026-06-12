"""AC-C4..AC-C8: Pipeline SKILL.md feasibility re-route wiring.

Asserts that skills/pipeline/SKILL.md:
  - Step 2d has a distinct PLAN_FEASIBILITY_REJECTED branch separate from
    CHANGES_REQUESTED (AC-C4)
  - Single-reject wins over a concurrent overturn, evaluated BEFORE re-plan (AC-C5)
  - Recovery handler is positioned after PLAN_ESCALATED, before Review
    CHANGES_REQUESTED; surfaces to user; NOT silent re-work; writes
    feasibility_drift before stop (AC-C6)
  - Re-plan branch documented when BOTH challengers overturn architect reject (AC-C7)
  - 4d-i conditional block writes phases.plan_validation.feasibility_drift with
    overturned:false on FEASIBLE-agreed; absent only when no pass ran (AC-C8)

Markdown-grep tests — no production code dependency.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "skills" / "pipeline" / "SKILL.md"


def _skill_text() -> str:
    return SKILL.read_text()


def _step_2d_section() -> str:
    """Return the text of the 'Collect verdicts' subsection of Step 2d."""
    text = _skill_text()
    # The section starts with '3. Collect verdicts:' and ends before '4. After validation'
    m = re.search(
        r"3\.\s+Collect verdicts:(.+?)(?=\n\d+\.\s+After validation|\n###\s+|\Z)",
        text,
        re.DOTALL,
    )
    return m.group(0) if m else ""


def _recovery_section() -> str:
    """Return the full Step 4 Recovery Loops section."""
    text = _skill_text()
    m = re.search(
        r"### Step 4: Recovery Loops(.+?)(?=\n###\s+|\Z)",
        text,
        re.DOTALL,
    )
    return m.group(0) if m else ""


def _step_4d_i_section() -> str:
    """Return the 4d-i observation-append section."""
    text = _skill_text()
    m = re.search(
        r"####\s+4d-i\.[^\n]*\n(.+?)(?=\n####\s+|\n###\s+|\n##\s+|\Z)",
        text,
        re.DOTALL,
    )
    return m.group(0) if m else ""


class TestStep2dHasDistinctFeasibilityRejectBranch(unittest.TestCase):
    """AC-C4: Step 2d 'Collect verdicts' has a PLAN_FEASIBILITY_REJECTED
    branch separate from the CHANGES_REQUESTED branch.
    """

    def test_step2d_has_distinct_feasibility_reject_branch(self):
        section = _step_2d_section()
        self.assertTrue(section, "Step 2d 'Collect verdicts' section not found")
        self.assertIn(
            "PLAN_FEASIBILITY_REJECTED",
            section,
            "PLAN_FEASIBILITY_REJECTED branch missing from Step 2d",
        )
        self.assertIn(
            "CHANGES_REQUESTED",
            section,
            "CHANGES_REQUESTED still must appear (contrast)",
        )
        # They must be at different positions — distinct branches
        pfr_pos = section.find("PLAN_FEASIBILITY_REJECTED")
        cr_pos = section.find("CHANGES_REQUESTED")
        self.assertNotEqual(
            pfr_pos, cr_pos,
            "PLAN_FEASIBILITY_REJECTED and CHANGES_REQUESTED must be separate branches",
        )


class TestSplitVerdictAnySingleRejectWins(unittest.TestCase):
    """AC-C5: Step 2d documents that ANY single PLAN_FEASIBILITY_REJECTED
    (even paired with APPROVE/overturn) resolves to PLAN_FEASIBILITY_REJECTED,
    and this rule is evaluated BEFORE the re-plan branch.
    """

    def test_split_verdict_any_single_reject_wins(self):
        section = _step_2d_section()
        self.assertTrue(section, "Step 2d 'Collect verdicts' section not found")
        text = _skill_text()

        # "any single" or equivalent language
        has_single_wins = bool(
            re.search(
                r"[Aa]ny\s+single\s+PLAN_FEASIBILITY_REJECTED|"
                r"one\s+.*PLAN_FEASIBILITY_REJECTED.*wins|"
                r"PLAN_FEASIBILITY_REJECTED.*single.*rejector",
                section,
                re.IGNORECASE | re.DOTALL,
            )
        )
        self.assertTrue(
            has_single_wins,
            "Step 2d must document 'any single PLAN_FEASIBILITY_REJECTED wins'",
        )

        # Precedence: the single-reject rule is evaluated BEFORE the re-plan branch
        # Both must be present and single-reject text precedes re-plan text
        single_reject_pos = text.find("Any single PLAN_FEASIBILITY_REJECTED")
        if single_reject_pos == -1:
            single_reject_pos = text.lower().find(
                "any single plan_feasibility_rejected"
            )
        replan_pos = re.search(
            r"re-spawn architect to author the (skipped|full) plan",
            text,
            re.IGNORECASE,
        )
        self.assertNotEqual(
            single_reject_pos, -1,
            "Single-reject wins rule not found in SKILL.md",
        )
        self.assertIsNotNone(
            replan_pos, "Re-plan branch not found in SKILL.md"
        )
        self.assertLess(
            single_reject_pos,
            replan_pos.start(),
            "Single-reject rule must appear BEFORE the re-plan branch (precedence order)",
        )


class TestRecoveryHandlerSurfacesToUserNotSilentRework(unittest.TestCase):
    """AC-C6: The PLAN_FEASIBILITY_REJECTED recovery handler is:
    - positioned after PLAN_ESCALATED, before Review CHANGES_REQUESTED
    - surfaces to the user (not silent re-work)
    - writes feasibility_drift BEFORE the stop
    """

    def test_recovery_handler_surfaces_to_user_not_silent_rework(self):
        text = _skill_text()

        # Handler heading must exist
        self.assertIn(
            "#### Plan Validation PLAN_FEASIBILITY_REJECTED",
            text,
            "Recovery handler heading missing",
        )

        # Positioned AFTER PLAN_ESCALATED
        escalated_pos = text.find("#### Plan Validation PLAN_ESCALATED")
        pfr_pos = text.find("#### Plan Validation PLAN_FEASIBILITY_REJECTED")
        review_cr_pos = text.find("#### Review CHANGES_REQUESTED")

        self.assertNotEqual(escalated_pos, -1, "PLAN_ESCALATED heading missing")
        self.assertNotEqual(pfr_pos, -1, "PLAN_FEASIBILITY_REJECTED heading missing")
        self.assertNotEqual(review_cr_pos, -1, "Review CHANGES_REQUESTED heading missing")

        self.assertLess(
            escalated_pos,
            pfr_pos,
            "PLAN_FEASIBILITY_REJECTED handler must come AFTER PLAN_ESCALATED",
        )
        self.assertLess(
            pfr_pos,
            review_cr_pos,
            "PLAN_FEASIBILITY_REJECTED handler must come BEFORE Review CHANGES_REQUESTED",
        )

        # Extract the handler body (from heading to next heading)
        m = re.search(
            r"#### Plan Validation PLAN_FEASIBILITY_REJECTED(.+?)(?=\n####\s+|\Z)",
            text,
            re.DOTALL,
        )
        body = m.group(1) if m else ""
        self.assertTrue(body, "PLAN_FEASIBILITY_REJECTED handler body empty")

        # Surfaces to user (not silent)
        self.assertTrue(
            re.search(r"surface|user.*verbatim|verbatim.*user", body, re.IGNORECASE),
            "Handler must surface to the user (not silent re-work)",
        )

        # Must NOT be the same as the silent CHANGES_REQUESTED re-work
        self.assertTrue(
            re.search(r"NOT.*silent|NOT.*PLAN_CHANGES_REQUESTED|distinct from", body, re.IGNORECASE),
            "Handler must explicitly distinguish itself from silent PLAN_CHANGES_REQUESTED re-work",
        )

        # Writes feasibility_drift BEFORE the stop
        drift_pos = body.find("feasibility_drift")
        # "stop" or "pipeline stops" or "Blocked"
        stop_m = re.search(r"stop|Blocked", body)
        self.assertNotEqual(
            drift_pos, -1,
            "Handler must write feasibility_drift",
        )
        self.assertIsNotNone(stop_m, "Handler must reference pipeline stop / Blocked")
        self.assertLess(
            drift_pos,
            stop_m.start(),
            "feasibility_drift write must appear BEFORE the stop reference",
        )


class TestReplanBranchWhenBothOverturnAReject(unittest.TestCase):
    """AC-C7: A branch re-spawns the architect to author the skipped full plan
    when BOTH challengers overturn an architect FEASIBILITY_REJECTED (no single
    reject present), without stopping.
    """

    def test_replan_branch_when_both_overturn_a_reject(self):
        section = _step_2d_section()
        self.assertTrue(section, "Step 2d section not found")

        # Must document the re-plan when BOTH overturn
        has_both_overturn = bool(
            re.search(
                r"BOTH\s+challengers.*overturn|both.*APPROVE-with-overturn|"
                r"both.*overturn.*FEASIBILITY_REJECTED",
                section,
                re.IGNORECASE | re.DOTALL,
            )
        )
        self.assertTrue(
            has_both_overturn,
            "Step 2d must document the BOTH-overturn re-plan branch",
        )

        # Must say "re-spawn architect" or equivalent
        has_respawn = bool(
            re.search(
                r"re-spawn\s+architect|respawn.*architect",
                section,
                re.IGNORECASE,
            )
        )
        self.assertTrue(
            has_respawn,
            "Step 2d must document re-spawning the architect on both-overturn",
        )

        # Must say pipeline does NOT stop
        has_not_stop = bool(
            re.search(
                r"Do\s+NOT\s+stop|does\s+not\s+stop|pipeline.*not.*stop",
                section,
                re.IGNORECASE,
            )
        )
        self.assertTrue(
            has_not_stop,
            "Step 2d re-plan branch must state pipeline does NOT stop",
        )


class TestFeasibilityDriftWrittenWithOverturnedFalseOnAgree(unittest.TestCase):
    """AC-C8: The 4d-i block conditionally writes phases.plan_validation.feasibility_drift
    with {architect_said, reviewers_concluded, overturned} when a pass ran.
    On FEASIBLE-agreed, overturned:false is written (present, not omitted).
    Absent only when no pass ran (mirrors persona_rejections absence-vs-null rule).
    """

    def test_feasibility_drift_written_with_overturned_false_on_agree(self):
        body = _step_4d_i_section()
        self.assertTrue(body, "4d-i section not found")

        # Must document phases.plan_validation.feasibility_drift
        self.assertIn(
            "plan_validation",
            body,
            "4d-i must reference phases.plan_validation.feasibility_drift",
        )
        self.assertIn(
            "feasibility_drift",
            body,
            "4d-i must document feasibility_drift conditional block",
        )

        # Must document architect_said field
        self.assertIn(
            "architect_said",
            body,
            "feasibility_drift block must document architect_said field",
        )

        # Must document reviewers_concluded field
        self.assertIn(
            "reviewers_concluded",
            body,
            "feasibility_drift block must document reviewers_concluded field",
        )

        # Must document overturned field
        self.assertIn(
            "overturned",
            body,
            "feasibility_drift block must document overturned field",
        )

        # overturned:false on FEASIBLE-agreed (must be present, not omitted)
        has_false_on_agree = bool(
            re.search(
                r"overturned.*:.*false|overturned.*false.*FEASIBLE|"
                r"both.*agreed.*FEASIBLE.*overturned.*false|"
                r"overturned:false",
                body,
                re.IGNORECASE | re.DOTALL,
            )
        )
        self.assertTrue(
            has_false_on_agree,
            "4d-i must document overturned:false when pass ran and both agreed FEASIBLE",
        )

        # Absence only when no pass ran (not on outcome)
        has_absence_rule = bool(
            re.search(
                r"absent.*no.*pass|absent.*pass.*did.?n.?t|"
                r"omission.*pass.?didn.?t.?run|no.*feasibility.*pass.*absent|"
                r"absent.*only.*pass.*not.*run|absent.*when.*no.*pass",
                body,
                re.IGNORECASE | re.DOTALL,
            )
        )
        self.assertTrue(
            has_absence_rule,
            "4d-i must state absence is reserved for pass-didn't-run (not outcome)",
        )


if __name__ == "__main__":
    unittest.main()
