"""AC4 — Step 5b documents the canonical env-hatch shape
(`CLAUDE_DISABLE_SANDBOX_VERIFY=1`) and the `**Escape hatch.**` prose
heading style used by sibling skills (PBT, security-review, auto-learn).
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = (
    REPO_ROOT / "skills" / "build-implementation" / "SKILL.md"
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _step_5b_helpers import step_5b_body  # noqa: E402


class Step5bDocumentsEnvHatch(unittest.TestCase):
    """AC4 contract: canonical env-hatch shape AND prose heading."""

    def setUp(self):
        self.text = SKILL_PATH.read_text()
        self.body = step_5b_body(self.text)

    def test_ac4_step_5b_documents_canonical_env_hatch_style(self):
        self.assertNotEqual(
            self.body, "",
            "Step 5b heading not found in build-implementation SKILL.md")
        self.assertIn(
            "**Escape hatch.**",
            self.body,
            "Step 5b body must use the canonical `**Escape hatch.**` "
            "heading style (matches PBT Step 1d at SKILL.md:73)")
        self.assertIn(
            "CLAUDE_DISABLE_SANDBOX_VERIFY=1",
            self.body,
            "Step 5b body must document the canonical env-hatch "
            "`CLAUDE_DISABLE_SANDBOX_VERIFY=1` (matches the 8 existing "
            "`CLAUDE_DISABLE_*=1` hatches in the harness)")
        # The env-hatch reason token must match Story-1's PBT precedent
        # byte-for-byte so forensics greps on both surfaces.
        self.assertIn(
            "env-hatch",
            self.body,
            "Step 5b body must enumerate `env-hatch` as the skip reason "
            "(matches PBT_SKIPPED reason token at verdict-catalog.md:39)")


if __name__ == "__main__":
    unittest.main()
