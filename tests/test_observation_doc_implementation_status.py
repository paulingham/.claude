"""AC9: documentation correctness regression.

The `Implementation status` paragraph at
`protocols/autonomous-intelligence.md` § Field reference must
correctly cite the regular-pipeline observation writer. PR #105
shipped the consumer (`mine_anti_patterns`) but the existing prose
falsely claimed "the per-pipeline writer lives in
`skills/pipeline/SKILL.md`" — Step 7 of that skill had no observation
writer at all.

This test pins the corrected citation: Implementation Status now
references `Step 7b-bis` (the new regular-pipeline writer) AND the
existing batch-pipeline `Step 6` writer.

Per challenger Finding 2, the assertion is intentionally tight:
drift between this paragraph and the actual SKILL.md heading IS the
regression we want surfaced. If a future refactor renumbers the
step, both this test AND the SKILL.md must be updated together.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC = REPO_ROOT / "protocols" / "autonomous-intelligence.md"


def _implementation_status_paragraph() -> str:
    """Return the `Implementation status` paragraph from § Field reference.

    The paragraph is delimited as one block-level item — bold-prefixed
    with `**Implementation status` and ending at the next blank line
    or section header.
    """
    text = DOC.read_text()
    match = re.search(
        r"\*\*Implementation status[^*]*\*\*[^\n]*(?:\n(?!\n)[^\n]*)*",
        text)
    return match.group(0) if match else ""


class TestImplementationStatusAccurate(unittest.TestCase):
    """AC9: paragraph cites the new producer-side step number AND no
    longer makes the false claim about a non-existent writer in
    skills/pipeline/SKILL.md.
    """

    def test_status_paragraph_references_step_7b_bis(self):
        para = _implementation_status_paragraph()
        self.assertTrue(
            para,
            "Implementation status paragraph not found at "
            "protocols/autonomous-intelligence.md § Field reference")
        # Must reference the new regular-pipeline writer step.
        self.assertIn(
            "Step 7b-bis", para,
            "Implementation status paragraph must cite "
            "`skills/pipeline/SKILL.md` Step 7b-bis")
        # Must continue to reference the batch-pipeline Step 6 writer.
        self.assertIn(
            "Step 6", para,
            "Implementation status paragraph must continue to cite "
            "`skills/batch-pipeline/SKILL.md` Step 6")

    def test_status_paragraph_does_not_make_false_pipeline_skill_claim(
            self):
        """The previous prose said `the per-pipeline writer lives in
        skills/pipeline/SKILL.md and skills/batch-pipeline/SKILL.md
        Step 6 / Step 7c` — Step 7c is /learn invocation, not a
        writer. This test pins the corrected wording: the paragraph
        must not claim the writer lives at Step 7c.
        """
        para = _implementation_status_paragraph()
        self.assertTrue(para, "paragraph not found")
        # The corrected paragraph cites Step 7b-bis as the writer
        # (not Step 7c). Assert the false "Step 7c" writer claim
        # is no longer present (Step 7c, the /learn invocation,
        # must NOT be cited as the per-pipeline writer site).
        # The text "Step 6 / Step 7c" was the false form; assert
        # that exact bigram is gone.
        self.assertNotIn(
            "Step 6 / Step 7c", para,
            "paragraph still contains the false Step 6 / Step 7c "
            "writer-citation pair; corrected wording must drop "
            "Step 7c (which is the /learn invocation)")


if __name__ == "__main__":
    unittest.main()
