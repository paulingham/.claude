"""Direct tests for _lib.paths defaults."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,
                str(Path(__file__).resolve().parents[1] /
                    "skills" / "reindex-memory"))

from _lib import paths  # noqa: E402


class DefaultsRootedAtClaudeHome(unittest.TestCase):
    def test_default_db_under_db_dir(self):
        self.assertEqual(paths.default_db().name, "memory.sqlite")
        self.assertEqual(paths.default_db().parent.name, "db")

    def test_default_learning_is_learning_dir(self):
        self.assertEqual(paths.default_learning().name, "learning")


if __name__ == "__main__":
    unittest.main()
