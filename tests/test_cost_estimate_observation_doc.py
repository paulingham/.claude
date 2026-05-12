"""B12.2: cost_estimate_usd field documented in observation JSONL.

Verifies:
- protocols/autonomous-intelligence.md § Observation Capture documents
  the new `cost_estimate_usd: number` field, its source, and the backward-
  compatibility note. The example JSONL block includes the field.
- skills/learn/SKILL.md mentions cost_estimate_usd correlation in a section
  OTHER than Step 1 / Step 1b / Step 10 (B8.1 owns those regions).
- The "tolerate absence in legacy records" note is present.
- The implementation-status disclosure (B12.3 follow-up) is present so the
  documented field is honestly disclosed as not-yet-emitted.
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC = REPO_ROOT / "protocols" / "autonomous-intelligence.md"
LEARN = REPO_ROOT / "skills" / "learn" / "SKILL.md"


def _observation_capture_section() -> str:
    """Return the body of `### Observation Capture` up to the next `### `/`## `."""
    text = DOC.read_text()
    match = re.search(
        r"###\s+Observation Capture\b(.+?)(?=\n###\s+|\n##\s+|\Z)",
        text, re.DOTALL)
    return match.group(1) if match else ""


def _learn_section_outside_step_1_and_10(needle: str) -> str:
    """Return the SKILL.md region containing `needle` IFF it is not inside
    Step 1, Step 1b, Step 1c, or Step 10 — scoped to the body of the
    enclosing `### N[x]. ...` step so that callers asserting word presence
    do not accidentally match keywords in unrelated steps elsewhere in the
    file. Returns '' when the needle falls inside a forbidden step.
    """
    text = LEARN.read_text()
    if needle not in text:
        return ""
    # Find every section header position with its label.
    headers = [(m.start(), m.group(1)) for m in re.finditer(
        r"###\s+(\d+[a-z]?)\.\s+", text)]
    needle_pos = text.index(needle)
    # Find the latest header before the needle (and the next header after,
    # to delimit the enclosing step body).
    enclosing = None
    enclosing_start = 0
    next_start = len(text)
    for pos, label in headers:
        if pos <= needle_pos:
            enclosing = label
            enclosing_start = pos
        else:
            next_start = pos
            break
    forbidden = {"1", "1b", "1c", "10"}
    if enclosing in forbidden:
        return ""
    return text[enclosing_start:next_start]


class ObservationCaptureDocumentsCostEstimateField(unittest.TestCase):
    def test_field_name_and_type_documented(self):
        body = _observation_capture_section()
        self.assertTrue(body, "§ Observation Capture not found")
        self.assertIn("cost_estimate_usd", body)
        # Type annotation: documented as `number` (USD float)
        self.assertRegex(body, r"`cost_estimate_usd`\s*[:\s].*?\bnumber\b",
                         msg="cost_estimate_usd must be typed as number")
        self.assertIn("USD", body)

    def test_source_references_cost_estimator_module(self):
        body = _observation_capture_section()
        self.assertIn("hooks/_lib/cost_estimator.py", body)
        self.assertIn("tool-timings.jsonl", body)
        self.assertIn("task_id", body)

    def test_backward_compatibility_note_present(self):
        body = _observation_capture_section()
        self.assertIn("Backward compatibility", body)
        self.assertRegex(
            body,
            r"tolerate\s+absence\s+of\s+`?cost_estimate_usd`?",
            msg="backward-compatibility note must say readers tolerate absence",
        )

    def test_example_jsonl_block_includes_field(self):
        body = _observation_capture_section()
        # The example JSONL block is delimited by ```bash ... ``` and contains
        # `"record_type": "pipeline"`. Find that block and assert the field
        # appears inside it.
        match = re.search(
            r"```(?:bash|json)?\n(.*?\"record_type\":\s*\"pipeline\".*?)\n```",
            body, re.DOTALL)
        self.assertIsNotNone(match,
                             "pipeline observation example block not found")
        self.assertIn("cost_estimate_usd", match.group(1))

    def test_implementation_status_disclosure_present(self):
        body = _observation_capture_section()
        self.assertIn("Implementation status", body)
        self.assertIn("B12.3", body)


class LearnSkillCorrelatesCostWithQualityOutsideStep1And10(unittest.TestCase):
    def test_learn_mentions_cost_estimate_usd_outside_steps_1_and_10(self):
        text = _learn_section_outside_step_1_and_10("cost_estimate_usd")
        self.assertTrue(
            text,
            "skills/learn/SKILL.md must mention cost_estimate_usd in a "
            "section other than Step 1/1b/1c/10")

    def test_learn_describes_correlation_with_quality_outcomes(self):
        # Scope the assertions to the post-Step-7b region so that the
        # `rounds` / `rework` keywords being asserted are the ones inside
        # the cost-quality correlation step itself, not unrelated mentions
        # elsewhere in the file (the same words appear in multiple steps).
        scoped = _learn_section_outside_step_1_and_10("cost_estimate_usd")
        self.assertTrue(
            scoped,
            "skills/learn/SKILL.md must mention cost_estimate_usd in a "
            "section other than Step 1/1b/1c/10")
        # The cost-quality correlation step must reference at least three
        # quality dimensions captured in the same observation record.
        self.assertRegex(scoped, r"\brounds\b",
                         msg="correlation must reference review rounds")
        self.assertRegex(scoped, r"\brework\b",
                         msg="correlation must reference rework rate")
        self.assertRegex(scoped, r"role.*task[- ]class|task[- ]class.*role",
                         msg="correlation must aggregate per (role, task-class)")

    def test_learn_feeds_correlation_into_existing_instinct_logic(self):
        text = LEARN.read_text()
        self.assertIn("prefer_opus", text)
        # The new step must reference how its output feeds existing logic.
        self.assertRegex(
            text,
            r"(model[- ]effectiveness|model-recommendations)",
            msg="correlation output must feed model-effectiveness recs",
        )


if __name__ == "__main__":
    unittest.main()
