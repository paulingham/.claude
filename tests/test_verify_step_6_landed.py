"""Slice 2: /verify SKILL.md gains Step 6 — Write Verification Evidence State File.

The step lands between current `### 5. Produce Verification Report` (line 177)
and `## Output Format` (line 179). It MUST:
  - document the new schema fields (task_id, git_head, generated_at, verdict, tier_results, sandbox_run)
  - name `_psp_verification_evidence_path` as the path resolver
  - specify `os.replace` atomic-rename write shape
  - resolve write target relative to $CLAUDE_REPO_ROOT (not cwd)
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VERIFY_SKILL = REPO_ROOT / "skills" / "verify" / "SKILL.md"


class VerifyStep6Landed(unittest.TestCase):
    def setUp(self):
        self.text = VERIFY_SKILL.read_text()

    def test_verify_skill_contains_step_6_heading(self):
        # Exactly one Step 6 heading naming the state-file write.
        matches = re.findall(r"^### 6\. .*Verification Evidence.*State File",
                             self.text, re.MULTILINE)
        self.assertEqual(len(matches), 1,
                         f"expected exactly one Step 6 heading, found {matches}")

    def test_verify_step_6_documents_schema_fields(self):
        # All schema fields from plan.md § API Contracts must be named in the prose.
        for field in ("schema_version", "task_id", "git_head", "generated_at",
                      "verdict", "tier_results", "sandbox_run"):
            self.assertIn(field, self.text,
                          f"Step 6 must document schema field `{field}`")

    def test_verify_step_6_names_psp_helper_and_repo_root(self):
        # Helper name + CLAUDE_REPO_ROOT resolution (not cwd-relative).
        self.assertIn("_psp_verification_evidence_path", self.text)
        self.assertIn("CLAUDE_REPO_ROOT", self.text)

    def test_verify_step_6_documents_os_replace_atomic_rename(self):
        # Atomicity contract per plan.md § Slices > Slice 2.
        self.assertIn("os.replace", self.text)
        self.assertIn("atomic", self.text.lower())

    def test_verify_step_6_landing_position_between_step_5_and_output_format(self):
        # Position contract: Step 6 falls between `### 5. Produce Verification Report`
        # and `## Output Format`.
        step5 = self.text.find("### 5. Produce Verification Report")
        step6 = self.text.find("### 6.")
        output_format = self.text.find("## Output Format")
        self.assertGreater(step5, -1, "Step 5 heading must exist")
        self.assertGreater(step6, step5,
                           "Step 6 must come after Step 5")
        self.assertLess(step6, output_format,
                        "Step 6 must come before ## Output Format")

    def test_verify_step_6_proposal_reference(self):
        # Step 6 must cite the proposal file for the field definitions.
        self.assertIn("2026-05-14-iron-law-2-freshness-hook.md", self.text)


if __name__ == "__main__":
    unittest.main()
