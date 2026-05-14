"""Slice 5: agents/patch-critic.md Operating Discipline paragraph gains an
APPENDED sentence pointing at hooks/verification-freshness-guard.sh.

LOW-PR2: edit uses the trailing parenthetical as unique anchor (the broader
'halt and report' phrase appears earlier in the paragraph).
"""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PATCH_CRITIC = REPO_ROOT / "agents" / "patch-critic.md"


class PatchCriticProseAppended(unittest.TestCase):
    def setUp(self):
        self.text = PATCH_CRITIC.read_text()

    def test_patch_critic_md_appends_hook_reference(self):
        # Original sentence must remain present (append-only edit).
        self.assertIn(
            "halt and report. Never fabricate or assume what the result would have been.",
            self.text,
            "original Operating Discipline prose must survive")
        # New sentence MUST follow.
        self.assertIn("verification-freshness-guard.sh", self.text)
        self.assertIn("Enforcement:", self.text)

    def test_patch_critic_appended_sentence_mentions_v2_1_141(self):
        self.assertIn("v2.1.141", self.text)
        self.assertIn("permissionDecision", self.text)

    def test_patch_critic_appended_sentence_references_input_table(self):
        """S5 depends on S4 for the verification-evidence input row that the
        hook is gating against. The append must mention the spawn-time
        contract verb."""
        self.assertIn("log-only", self.text)


if __name__ == "__main__":
    unittest.main()
