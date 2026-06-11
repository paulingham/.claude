"""Guard: skills/embedder/SKILL.md must NOT exist; README.md MUST exist with known markers.

This test is RED before the rename (SKILL.md still present, README.md absent).
After `git mv skills/embedder/SKILL.md skills/embedder/README.md` it goes GREEN.
"""
from pathlib import Path
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
_EMBEDDER_DIR = REPO_ROOT / "skills" / "embedder"
_OLD_PATH = _EMBEDDER_DIR / "SKILL.md"
_NEW_PATH = _EMBEDDER_DIR / "README.md"

_KNOWN_MARKERS = [
    "name: embedder",
    "## Requirements",
    "### Linux",
]


class EmbedderSkillMdRelocated(unittest.TestCase):
    def test_skill_md_is_absent(self):
        """SKILL.md must not exist after the rename."""
        self.assertFalse(
            _OLD_PATH.exists(),
            f"skills/embedder/SKILL.md still exists; run: git mv {_OLD_PATH} {_NEW_PATH}",
        )

    def test_readme_md_exists(self):
        """README.md must exist after the rename."""
        self.assertTrue(
            _NEW_PATH.exists(),
            f"skills/embedder/README.md is missing; run: git mv {_OLD_PATH} {_NEW_PATH}",
        )

    def test_readme_md_contains_known_markers(self):
        """README.md content must carry the known markers from the old SKILL.md."""
        self.assertTrue(_NEW_PATH.exists(), "README.md missing — rename not done yet")
        text = _NEW_PATH.read_text()
        for marker in _KNOWN_MARKERS:
            self.assertIn(marker, text, f"README.md is missing expected marker: {marker!r}")


if __name__ == "__main__":
    unittest.main()
