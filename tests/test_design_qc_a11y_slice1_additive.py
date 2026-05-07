"""AC17 — Slice 1 is behaviorally additive for downstream agents.

Verifies that the design-qc skill, when interpreted post-Slice-1 and
pre-Slice-2:
- still emits SCREENSHOTS_CAPTURED (no verdict change)
- introduces no new scratchpad finding categories beyond
  {discovery, warning, pattern, fragility, decision}
- introduces no new pipeline-state file paths consumed by other agents
  beyond what existed pre-B4 (specifically: agents/product-reviewer.md
  and skills/patch-critique/SKILL.md MUST NOT yet reference the new
  index.json path until Slice 2 lands)

Because Slice 1 + Slice 2 are shipped together in this PR, the only
behaviour we can directly assert is the scratchpad-category invariant
plus the design-qc verdict invariant.
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DESIGN_QC = REPO_ROOT / "skills" / "design-qc" / "SKILL.md"

SCRATCHPAD_CATEGORIES = {
    "discovery", "warning", "pattern", "fragility", "decision"
}


class DesignQcVerdictInvariants(unittest.TestCase):
    """Slice 1 must not change the design-qc verdict surface."""

    def test_design_qc_still_emits_screenshots_captured(self):
        text = DESIGN_QC.read_text()
        self.assertIn("SCREENSHOTS_CAPTURED", text)

    def test_design_qc_still_emits_capture_failed(self):
        text = DESIGN_QC.read_text()
        self.assertIn("CAPTURE_FAILED", text)

    def test_design_qc_does_not_introduce_new_verdict(self):
        # Allowed verdicts in design-qc Phase Output / Failure Modes table.
        # If a new verdict appears, this test must be updated deliberately.
        text = DESIGN_QC.read_text()
        # Look for capitalised TOKEN_TOKEN style strings in Verdict column.
        verdicts = set(re.findall(
            r"Verdict:\s*([A-Z_]+(?:\s*/\s*[A-Z_]+)*)", text))
        flat = set()
        for entry in verdicts:
            for tok in re.split(r"\s*/\s*", entry):
                flat.add(tok.strip())
        # Must contain the two known verdicts and NOTHING ELSE.
        self.assertIn("SCREENSHOTS_CAPTURED", flat)
        self.assertIn("CAPTURE_FAILED", flat)
        unexpected = flat - {"SCREENSHOTS_CAPTURED", "CAPTURE_FAILED"}
        self.assertEqual(
            unexpected, set(),
            f"design-qc has new verdicts not in the Slice-1 invariant: "
            f"{unexpected!r}")


class ScratchpadCategoryInvariant(unittest.TestCase):
    """Slice 1 must not invent new scratchpad categories."""

    def test_design_qc_a11y_section_uses_only_allowed_categories(self):
        text = DESIGN_QC.read_text()
        # Find category: lines (YAML frontmatter style).
        cats = set(re.findall(r"category:\s*([a-z\-]+)", text))
        unknown = cats - SCRATCHPAD_CATEGORIES
        self.assertEqual(
            unknown, set(),
            f"unknown scratchpad categories used in design-qc: {unknown!r}")


if __name__ == "__main__":
    unittest.main()
