"""AC1-AC5: regular-pipeline + batch-pipeline observation writer documentation.

Asserts the producer-side documentation contract for
`phases.patch_critic.persona_rejections` lives in BOTH skill files:

- `skills/pipeline/SKILL.md` Step 7b-bis (regular pipeline, NEW)
- `skills/batch-pipeline/SKILL.md` Step 6 (batch pipeline, EXTENDED)

Mirrors the fenced-code-block matcher pattern from
`tests/test_cost_estimate_observation_doc.py::test_example_jsonl_block_includes_field`.

Markdown-grep tests — no production code dependency.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_SKILL = REPO_ROOT / "skills" / "pipeline" / "SKILL.md"
BATCH_SKILL = REPO_ROOT / "skills" / "batch-pipeline" / "SKILL.md"


def _step_7b_bis_body() -> str:
    """Return the per-pipeline observation-capture step body.

    The observation-capture producer surface was RELOCATED from Step 7b-bis to
    Step 4d-i (Reflect-write, pre-Ship) so the artifacts ship inside the
    feature-branch PR. Step 7b-bis is now a pointer stub; the JSON template,
    mode invariant, and severity threshold live under `#### 4d-i.`. Extract
    that section (up to the next same-or-higher-level heading).
    """
    text = PIPELINE_SKILL.read_text()
    match = re.search(
        r"####\s+4d-i\.[^\n]*\n(.+?)(?=\n####\s+|\n###\s+|\n##\s+|\Z)",
        text, re.DOTALL)
    return match.group(0) if match else ""


def _step_6_body() -> str:
    """Return the body of Step 6 from skills/batch-pipeline/SKILL.md."""
    text = BATCH_SKILL.read_text()
    match = re.search(
        r"###\s+Step 6:[^\n]*\n(.+?)(?=\n###\s+|\n##\s+|\Z)",
        text, re.DOTALL)
    return match.group(0) if match else ""


def _fenced_json_block(body: str) -> str:
    """Return the inside of the first fenced JSON code block in `body`.

    Tolerates leading whitespace on the opening fence — list-indented
    fences (e.g. inside a numbered list) keep the ` ```json` indented
    three spaces in the source markdown.
    """
    match = re.search(
        r"^[ \t]*```(?:json|bash)?\n(.*?)^[ \t]*```",
        body, re.DOTALL | re.MULTILINE)
    return match.group(1) if match else ""


class TestStep7bBisExists(unittest.TestCase):
    """AC1: Pipeline SKILL.md contains a `### 7b-bis.` (or equivalent)
    header between `#### 7b. Qualitative Reflection` and
    `#### 7c. Learning Extraction`.
    """

    def test_pipeline_skill_step_7b_bis_exists(self):
        text = PIPELINE_SKILL.read_text()
        # Locate the three anchor headings.
        bis_match = re.search(r"####\s+7b-bis\.", text)
        self.assertIsNotNone(
            bis_match,
            "Step 7b-bis header missing from skills/pipeline/SKILL.md")
        b_pos = text.find("#### 7b. Qualitative Reflection")
        c_pos = text.find("#### 7c. Learning Extraction")
        self.assertNotEqual(b_pos, -1, "Step 7b heading missing")
        self.assertNotEqual(c_pos, -1, "Step 7c heading missing")
        bis_pos = bis_match.start()
        self.assertLess(b_pos, bis_pos,
                        "Step 7b-bis must come AFTER Step 7b")
        self.assertLess(bis_pos, c_pos,
                        "Step 7b-bis must come BEFORE Step 7c")


class TestStep7bBisDocumentsPhasesPatchCriticBlock(unittest.TestCase):
    """AC2: the new step's fenced JSON block contains the literal
    tokens `phases.patch_critic`, `verdict`, `rounds`, `mode`, and
    `persona_rejections`.
    """

    def test_step_7b_bis_documents_phases_patch_critic_block(self):
        body = _step_7b_bis_body()
        self.assertTrue(body, "Step 7b-bis body not found")
        block = _fenced_json_block(body)
        self.assertTrue(block, "fenced JSON block missing in Step 7b-bis")
        self.assertIn("patch_critic", block)
        self.assertIn("verdict", block)
        self.assertIn("rounds", block)
        self.assertIn("mode", block)
        self.assertIn("persona_rejections", block)


class TestStep7bBisDocumentsModeInvariant(unittest.TestCase):
    """AC3: the step body documents the iron rule:
    `persona_rejections` is present iff `mode == "multi-persona"`;
    absent in `single-critic` mode.
    """

    def test_step_7b_bis_documents_mode_invariant(self):
        body = _step_7b_bis_body()
        self.assertTrue(body, "Step 7b-bis body not found")
        # Both mode names must appear.
        self.assertIn("multi-persona", body)
        self.assertIn("single-critic", body)
        # Locate the literal "absent in single-critic" phrasing
        # (case-insensitive).
        body_lower = body.lower()
        self.assertIn(
            "absent in single-critic", body_lower,
            "Step 7b-bis must literally say `absent in single-critic`")


class TestStep7bBisDocumentsSeverityThreshold(unittest.TestCase):
    """AC4: the step body explicitly names `MEDIUM`, `HIGH`, `CRITICAL`
    AND states LOW/INFO are excluded.
    """

    def test_step_7b_bis_documents_severity_threshold(self):
        body = _step_7b_bis_body()
        self.assertTrue(body, "Step 7b-bis body not found")
        self.assertIn("CRITICAL", body)
        self.assertIn("HIGH", body)
        self.assertIn("MEDIUM", body)
        # LOW + INFO must be cited as excluded.
        self.assertIn("LOW", body)
        self.assertIn("INFO", body)
        self.assertRegex(
            body, r"(exclud|omit|drop).*LOW|LOW.*(exclud|omit|drop)",
            msg="Step 7b-bis must say LOW is excluded/omitted")


class TestBatchPipelineStep6IncludesPatchCriticBlock(unittest.TestCase):
    """AC5: skills/batch-pipeline/SKILL.md Step 6 fenced JSON template
    includes the `phases.patch_critic` block with the four key tokens
    (verdict, rounds, mode, persona_rejections) — no skew.
    """

    def test_batch_pipeline_step_6_includes_patch_critic_block(self):
        body = _step_6_body()
        self.assertTrue(body, "Batch Step 6 body not found")
        block = _fenced_json_block(body)
        self.assertTrue(block, "fenced JSON block missing in Batch Step 6")
        self.assertIn("patch_critic", block)
        self.assertIn("verdict", block)
        self.assertIn("rounds", block)
        self.assertIn("mode", block)
        self.assertIn("persona_rejections", block)


class TestFeasibilityDriftConditionalBlock(unittest.TestCase):
    """AC-C8 (slice-c update): 4d-i block documents phases.plan_validation.feasibility_drift
    conditional append with:
    - the three fields: architect_said, reviewers_concluded, overturned
    - overturned:false present on FEASIBLE-agreed (not omitted)
    - absence reserved for pass-didn't-run (not written as null)
    Mirror of persona_rejections absence-vs-null rule (SKILL.md:520).
    """

    def test_feasibility_drift_conditional_block_documented(self):
        body = _step_7b_bis_body()
        self.assertTrue(body, "4d-i section not found")
        self.assertIn(
            "feasibility_drift",
            body,
            "4d-i must document the feasibility_drift conditional block",
        )
        self.assertIn("architect_said", body)
        self.assertIn("reviewers_concluded", body)
        self.assertIn("overturned", body)

    def test_no_pass_emits_no_null_field(self):
        body = _step_7b_bis_body()
        self.assertTrue(body, "4d-i section not found")
        # Absence rule: when pass didn't run, omit the key (not null)
        has_absence_rule = bool(
            re.search(
                r"(absent.*only.*pass.*not.*run|"
                r"absent.*no.*pass|"
                r"omit.*key.*null|"
                r"do\s+NOT\s+write\s+null|"
                r"pass.*did.?n.?t.*run.*omit)",
                body,
                re.IGNORECASE | re.DOTALL,
            )
        )
        self.assertTrue(
            has_absence_rule,
            "4d-i must state absence is reserved for pass-didn't-run (not null)",
        )

    def test_overturned_false_present_on_feasible_agreed(self):
        body = _step_7b_bis_body()
        self.assertTrue(body, "4d-i section not found")
        has_false_present = bool(
            re.search(
                r"overturned.*:.*[Ff]alse|overturned.*false.*FEASIBLE|"
                r"both.*agreed.*FEASIBLE.*overturned.*false",
                body,
                re.IGNORECASE | re.DOTALL,
            )
        )
        self.assertTrue(
            has_false_present,
            "4d-i must document overturned:false (present, not omitted) on FEASIBLE-agreed",
        )


if __name__ == "__main__":
    unittest.main()
