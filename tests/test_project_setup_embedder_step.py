"""S9 AC10: /project-setup SKILL.md documents the embedder bootstrap step."""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "skills" / "project-setup" / "SKILL.md"


class SkillMdDocumentsEmbedderBootstrap(unittest.TestCase):
    def test_mentions_embedder_bootstrap_step(self):
        body = SKILL.read_text()
        self.assertIn("Embedder bootstrap", body)

    def test_mentions_bootstrap_command(self):
        body = SKILL.read_text()
        self.assertIn("python3 -m embedder._lib.bootstrap", body)

    def test_marks_step_as_macos_only(self):
        body = SKILL.read_text().lower()
        self.assertIn("macos", body)

    def test_documents_never_blocks_invariant(self):
        body = SKILL.read_text().lower()
        self.assertIn("never blocks", body)


if __name__ == "__main__":
    unittest.main()
