"""Slice slice-b-architect-feasibility-pass: agents/architect.md documents Feasibility Pass.

ACs from pipeline-state/plan-feasibility-finding/plan.md, slice-b:

- AC-B1: agents/architect.md contains `### Feasibility Pass` positioned AFTER
  `## Pre-Drafting Recon (Read First)` and BEFORE `## Pre-Emit Self-Review (Required)`.
- AC-B2: The section specifies the `## Feasibility Finding` output (verdict line +
  <=150-word evidence-cited brief, REJECT-BRIEF-ONLY default, no fallback plan).
- AC-B3: The section states verbatim that on `FEASIBILITY_REJECTED` the architect
  NEVER stops the pipeline and NEVER hard-rejects.
- AC-B4: The section instructs appending to `architect-context.md` (no new
  `feasibility.md`), with the orchestrator-persists fallback documented.
- AC-B5: The section documents the light-gate path: premise check still runs from
  the architect's own Reads, recorded inline in plan.md, consumed by
  `plan-self-validation` as a self-judgment with no overturn-to-feasible.
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ARCHITECT_MD = REPO_ROOT / "agents" / "architect.md"


def _read_architect_md() -> str:
    return ARCHITECT_MD.read_text()


def _section_body(heading: str, text: str) -> str:
    """Return the body following an exact `###` heading line, up to the next
    same-or-higher-level heading. Returns empty string if heading is absent."""
    pattern = rf"^{re.escape(heading)}\s*$(.*?)(?=^##\s|^###\s|\Z)"
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    return match.group(1) if match else ""


class FeasibilityPassSectionPosition(unittest.TestCase):
    """AC-B1 — section present and correctly positioned."""

    def test_feasibility_pass_section_between_recon_and_self_review(self):
        text = _read_architect_md()

        recon_heading = "## Pre-Drafting Recon (Read First)"
        feasibility_heading = "### Feasibility Pass (run before drafting)"
        self_review_heading = "## Pre-Emit Self-Review (Required)"

        recon_idx = text.find(recon_heading)
        feasibility_idx = text.find(feasibility_heading)
        self_review_idx = text.find(self_review_heading)

        self.assertGreater(
            recon_idx, -1,
            f"agents/architect.md must contain '{recon_heading}'",
        )
        self.assertGreater(
            feasibility_idx, -1,
            "agents/architect.md must contain '### Feasibility Pass (run before drafting)'",
        )
        self.assertGreater(
            self_review_idx, -1,
            f"agents/architect.md must contain '{self_review_heading}'",
        )
        self.assertGreater(
            feasibility_idx, recon_idx,
            "### Feasibility Pass must appear AFTER ## Pre-Drafting Recon (Read First)",
        )
        self.assertGreater(
            self_review_idx, feasibility_idx,
            "### Feasibility Pass must appear BEFORE ## Pre-Emit Self-Review (Required)",
        )


class FeasibilityRejectBriefContract(unittest.TestCase):
    """AC-B2 — reject-brief contract documented."""

    def test_reject_brief_contract_documented(self):
        text = _read_architect_md()
        body = _section_body("### Feasibility Pass (run before drafting)", text)
        self.assertTrue(body, "### Feasibility Pass section body must be non-empty")

        # Must specify the Feasibility Finding output section name
        self.assertIn(
            "## Feasibility Finding",
            body,
            "Feasibility Pass section must specify '## Feasibility Finding' as output section",
        )

        # Must specify the verdict line format
        self.assertIn(
            "FEASIBILITY: FEASIBLE",
            body,
            "Feasibility Pass section must document 'FEASIBILITY: FEASIBLE' verdict line",
        )
        self.assertIn(
            "FEASIBILITY: FEASIBILITY_REJECTED",
            body,
            "Feasibility Pass section must document 'FEASIBILITY: FEASIBILITY_REJECTED' verdict line",
        )

        # Must specify REJECT-BRIEF-ONLY as the default depth
        self.assertIn(
            "REJECT-BRIEF-ONLY",
            body,
            "Feasibility Pass section must specify REJECT-BRIEF-ONLY as default depth",
        )

        # Must state no fallback plan unless reviewers overturn
        self.assertRegex(
            body,
            r"no fallback plan|fallback plan unless|unless reviewers overturn",
            "Feasibility Pass section must state no fallback plan unless reviewers overturn",
        )

        # Must mention <=150-word evidence-cited brief
        self.assertRegex(
            body,
            r"150.word|150 word|<=\s*150",
            "Feasibility Pass section must specify the <=150-word evidence-cited brief",
        )


class ArchitectNeverSelfGates(unittest.TestCase):
    """AC-B3 — architect never stops pipeline / hard-rejects."""

    def test_architect_never_self_gates(self):
        text = _read_architect_md()
        body = _section_body("### Feasibility Pass (run before drafting)", text)
        self.assertTrue(body, "### Feasibility Pass section body must be non-empty")

        # Must state architect NEVER stops the pipeline
        self.assertRegex(
            body,
            r"NEVER stops the pipeline|never stops the pipeline",
            "Feasibility Pass section must state the architect NEVER stops the pipeline",
        )

        # Must state architect NEVER hard-rejects
        self.assertRegex(
            body,
            r"NEVER hard-rejects|never hard-rejects",
            "Feasibility Pass section must state the architect NEVER hard-rejects",
        )


class FeasibilityFindingAppendToArchitectContext(unittest.TestCase):
    """AC-B4 — instructs appending to architect-context.md with orchestrator-persists fallback."""

    def test_finding_written_to_existing_architect_context(self):
        text = _read_architect_md()
        body = _section_body("### Feasibility Pass (run before drafting)", text)
        self.assertTrue(body, "### Feasibility Pass section body must be non-empty")

        # Must instruct appending to architect-context.md
        self.assertIn(
            "architect-context.md",
            body,
            "Feasibility Pass section must instruct appending to architect-context.md",
        )
        # Must explicitly state "no new feasibility.md" (reject-D alternative) —
        # the substring "feasibility.md" is allowed ONLY when negated with "no new"
        self.assertRegex(
            body,
            r"no new [``]?feasibility\.md|no new feasibility",
            "Feasibility Pass section must explicitly state 'no new feasibility.md' "
            "(the design rejects creating a separate feasibility artifact)",
        )

        # Must document orchestrator-persists fallback
        self.assertRegex(
            body,
            r"orchestrator persists|orchestrator-persists|orchestrator.*persist",
            "Feasibility Pass section must document the orchestrator-persists fallback",
        )


class LightGatePremiseCheckDocumented(unittest.TestCase):
    """AC-B5 — light-gate path documented (no architect-context.md, inline in plan.md,
    plan-self-validation self-judgment, no overturn-to-feasible)."""

    def test_light_gate_premise_check_documented(self):
        text = _read_architect_md()
        body = _section_body("### Feasibility Pass (run before drafting)", text)
        self.assertTrue(body, "### Feasibility Pass section body must be non-empty")

        # Must mention the light-gate or light gate path
        self.assertRegex(
            body,
            r"light.gate|light gate",
            "Feasibility Pass section must document the light-gate path",
        )

        # Must state inline in plan.md when no architect-context.md
        self.assertIn(
            "plan.md",
            body,
            "Feasibility Pass section must state finding is recorded inline in plan.md on light gate",
        )

        # Must reference plan-self-validation consuming it
        self.assertIn(
            "plan-self-validation",
            body,
            "Feasibility Pass section must reference plan-self-validation as the consumer",
        )

        # Must state no overturn-to-feasible in light gate
        self.assertRegex(
            body,
            r"no overturn.to.feasible|no overturn-to-feasible",
            "Feasibility Pass section must state there is no overturn-to-feasible in the light gate",
        )


if __name__ == "__main__":
    unittest.main()
