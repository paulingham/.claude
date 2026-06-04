"""Tier 1 unit tests for design-qc SKILL.md doc-contract assertions.

Asserts that skills/design-qc/SKILL.md contains the required cross-reference
to the vlm-critic No-Diff Control Invariant (AC4b).
"""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESIGN_QC_SKILL = ROOT / "skills" / "design-qc" / "SKILL.md"


def _read(path):
    return path.read_text(encoding="utf-8")


class NoDiffControlCrossRef(unittest.TestCase):
    """AC4b — design-qc SKILL.md cross-references the vlm-critic No-Diff Control Invariant."""

    def test_design_qc_skill_md_has_vlm_critic_no_diff_cross_reference(self):
        """AC4b — design-qc SKILL.md names 'No-Diff Control Invariant'."""
        body = _read(DESIGN_QC_SKILL)
        self.assertIn(
            "No-Diff Control Invariant",
            body,
            "AC4b: skills/design-qc/SKILL.md must cross-reference the vlm-critic "
            "'No-Diff Control Invariant' section",
        )


if __name__ == "__main__":
    unittest.main()
