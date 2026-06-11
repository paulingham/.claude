"""Guard: the 3 content-reading guard files must not reference embedder/SKILL.md.

After repoint, none of the 3 guard files should contain the literal path
`embedder/SKILL.md`. This test is RED before the repoint and GREEN after.
"""
from pathlib import Path
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]

# The 3 guard files that previously hard-coded `embedder/SKILL.md`
_GUARD_FILES = [
    REPO_ROOT / "tests" / "test_skill_md_honesty.py",
    REPO_ROOT / "tests" / "test_s5_1_regression_guard.py",
    REPO_ROOT / "tests" / "shell" / "embedder-skill-portability.bats",
]

_STALE_REF = "embedder/SKILL.md"


class NoDanglingEmbedderSkillMdRefs(unittest.TestCase):
    def test_guard_files_do_not_reference_old_path(self):
        """After repoint, none of the 3 guard files reference embedder/SKILL.md."""
        hits = []
        for guard_path in _GUARD_FILES:
            self.assertTrue(guard_path.exists(), f"Guard file missing: {guard_path}")
            text = guard_path.read_text()
            if _STALE_REF in text:
                hits.append(str(guard_path))
        self.assertEqual(
            hits,
            [],
            f"These guard files still contain '{_STALE_REF}' — repoint them:\n"
            + "\n".join(f"  {h}" for h in hits),
        )


if __name__ == "__main__":
    unittest.main()
