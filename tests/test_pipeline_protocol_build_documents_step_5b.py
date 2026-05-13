"""Contract — `protocols/pipeline-protocol.md` § Phase Checklist Build bullet
mentions Step 5b as the sandbox-verify gate inside Build.

Surfaces to a forensic reader that the Build phase has TWO inline gates
(code-review + sandbox-verify), not one.
"""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_PROTOCOL = REPO_ROOT / "protocols" / "pipeline-protocol.md"


class PipelineProtocolBuildBulletMentionsStep5bSandboxGate(unittest.TestCase):
    """The § Phase Checklist Build bullet must mention Step 5b /
    sandbox-verify as a gate inside Build."""

    def test_pipeline_protocol_build_bullet_mentions_step_5b_sandbox_gate(self):
        text = PIPELINE_PROTOCOL.read_text()
        # Locate the Build bullet — bounded by next top-level checklist
        # bullet (`- **Review (Security)**:`).
        build_idx = text.find("- **Build**:")
        review_idx = text.find("- **Review (Security)**:")
        self.assertGreater(
            build_idx, -1,
            "protocols/pipeline-protocol.md must contain a `- **Build**:` "
            "checklist bullet")
        self.assertGreater(
            review_idx, build_idx,
            "the Build bullet must be followed by `- **Review (Security)**:`")
        build_section = text[build_idx:review_idx]
        # Step 5b OR sandbox-verify must be named in the Build bullet's
        # body so a forensic reader sees the second inline gate.
        self.assertTrue(
            "Step 5b" in build_section
            or "sandbox-verify" in build_section,
            "Build bullet must mention `Step 5b` or `sandbox-verify` so the "
            "second inline gate is discoverable from the phase checklist")


if __name__ == "__main__":
    unittest.main()
