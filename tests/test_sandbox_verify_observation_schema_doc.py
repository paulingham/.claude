"""AC1 — schema doc reflects `phases.sandbox_verify` row + producer comments.

Three snapshot-style tests on three doc files:

- `protocols/autonomous-intelligence.md` § Field reference contains a row
  for `phases.sandbox_verify` describing the schema (verdict, rounds,
  cost_estimate_usd, optional mode/divergence_count/skip_reason/
  diverging_tests). Mirrors the `phases.patch_critic` and
  `phases.pdr_rtv` precedent rows.
- `skills/pipeline/SKILL.md` Step 7b-bis JSON template mentions
  `phases.sandbox_verify` in a comment so the producer wiring is
  discoverable by the next reader.
- `skills/batch-pipeline/SKILL.md` Step 6 carries the same mention so
  regular-pipeline and batch-pipeline writers stay in lockstep.

The tests are deliberately string-shape assertions — the Field reference
text is the canonical spec, so the doc IS the contract.
"""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class SandboxVerifyRowExistsInFieldReference(unittest.TestCase):
    """`phases.sandbox_verify` row present in autonomous-intelligence.md."""

    def test_phases_sandbox_verify_row_exists(self):
        doc = (REPO_ROOT / "protocols" / "autonomous-intelligence.md").read_text()
        self.assertIn(
            "`phases.sandbox_verify`",
            doc,
            "Field reference MUST document `phases.sandbox_verify` row")

    def test_row_documents_required_keys(self):
        doc = (REPO_ROOT / "protocols" / "autonomous-intelligence.md").read_text()
        # Find the sandbox_verify row in the field reference table.
        # Required keys per Tier-0 C6: verdict, rounds, cost_estimate_usd.
        # Verdict enum: SANDBOX_VERIFIED | SANDBOX_FAILED | SANDBOX_SKIPPED.
        # Optional: mode, divergence_count (FAILED), skip_reason (SKIPPED),
        # diverging_tests (FAILED, bounded 20).
        # Find the row body so we don't false-positive on other doc text.
        row_idx = doc.find("`phases.sandbox_verify`")
        self.assertGreater(row_idx, -1)
        row_end = doc.find("\n\n", row_idx)
        if row_end == -1:
            row_end = len(doc)
        row_text = doc[row_idx:row_end]
        for needle in [
                "verdict",
                "rounds",
                "cost_estimate_usd",
                "SANDBOX_VERIFIED",
                "SANDBOX_FAILED",
                "SANDBOX_SKIPPED",
                "divergence_count",
                "skip_reason",
                "diverging_tests",
        ]:
            self.assertIn(
                needle, row_text,
                f"sandbox_verify row must mention {needle!r}")

    def test_row_documents_absence_tolerance(self):
        """Mirrors patch_critic / pdr_rtv precedent: absence != synthetic."""
        doc = (REPO_ROOT / "protocols" / "autonomous-intelligence.md").read_text()
        row_idx = doc.find("`phases.sandbox_verify`")
        row_end = doc.find("\n\n", row_idx)
        if row_end == -1:
            row_end = len(doc)
        row_text = doc[row_idx:row_end].lower()
        # Mirror language from patch_critic row.
        self.assertTrue(
            "tolerate absence" in row_text
            or "treat absence" in row_text
            or "absence" in row_text,
            "row must document absence-tolerance per patch_critic precedent")


class PipelineSkillJsonTemplateMentionsSandboxVerify(unittest.TestCase):
    """`skills/pipeline/SKILL.md` Step 7b-bis mentions phases.sandbox_verify."""

    def test_pipeline_step_7b_bis_mentions_sandbox_verify(self):
        doc = (REPO_ROOT / "skills" / "pipeline" / "SKILL.md").read_text()
        # Step 7b-bis is the producer surface for the regular pipeline.
        idx = doc.find("7b-bis")
        self.assertGreater(idx, -1, "Step 7b-bis header must exist")
        section = doc[idx:idx + 4000]
        self.assertIn(
            "sandbox_verify",
            section,
            "Step 7b-bis must reference phases.sandbox_verify "
            "so producer wiring is discoverable")


class BatchPipelineSkillJsonTemplateMentionsSandboxVerify(unittest.TestCase):
    """`skills/batch-pipeline/SKILL.md` Step 6 mentions phases.sandbox_verify."""

    def test_batch_pipeline_step_6_mentions_sandbox_verify(self):
        doc = (REPO_ROOT / "skills" / "batch-pipeline" / "SKILL.md").read_text()
        # Step 6: Reflect.
        idx = doc.find("Step 6")
        self.assertGreater(idx, -1, "Step 6 header must exist")
        section = doc[idx:idx + 4000]
        self.assertIn(
            "sandbox_verify",
            section,
            "Step 6 must reference phases.sandbox_verify "
            "for parity with the regular-pipeline writer")


if __name__ == "__main__":
    unittest.main()
