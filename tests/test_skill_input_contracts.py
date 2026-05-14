"""Slice 4: skill input contracts for the freshness state-file.

- skills/patch-critique/SKILL.md — Inputs table gets a new row.
- skills/verify/SKILL.md — gains a ## Inputs H2 (today it lists prereqs in prose).
- skills/product-acceptance/SKILL.md — gains an advisory checkbox (WARN, not BLOCK).
- skills/pr-creation/SKILL.md — notes the quality-gate dependency.
"""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PATCH_CRITIQUE = REPO_ROOT / "skills" / "patch-critique" / "SKILL.md"
VERIFY = REPO_ROOT / "skills" / "verify" / "SKILL.md"
PRODUCT_ACCEPT = REPO_ROOT / "skills" / "product-acceptance" / "SKILL.md"
PR_CREATION = REPO_ROOT / "skills" / "pr-creation" / "SKILL.md"


class SkillInputContracts(unittest.TestCase):
    def test_patch_critique_inputs_table_lists_verification_evidence(self):
        text = PATCH_CRITIQUE.read_text()
        # The new row references the state file produced by /verify Step 6.
        self.assertIn("verification-evidence.json", text)
        # The row mentions the source skill — /verify Step 6.
        self.assertRegex(text, r"/verify Step 6|verify.*Step 6")

    def test_verify_skill_has_inputs_h2_table(self):
        text = VERIFY.read_text()
        # New H2 must exist.
        self.assertIn("## Inputs", text)
        # Confirms the input row references the changed-files diff
        # that /verify already names in `Current Context`.
        self.assertIn("Candidate diff", text)

    def test_product_acceptance_advisory_checkbox_warn_only(self):
        text = PRODUCT_ACCEPT.read_text()
        self.assertIn("verification-evidence.json", text)
        # WARN-not-BLOCK invariant per architect-context.md § 4.
        self.assertIn("do NOT REJECT", text)

    def test_pr_creation_notes_quality_gate_dependency(self):
        text = PR_CREATION.read_text()
        # pr-creation must reference the quality-gate freshness check.
        self.assertIn("freshness", text.lower())
        self.assertIn("verification-evidence.json", text)


if __name__ == "__main__":
    unittest.main()
