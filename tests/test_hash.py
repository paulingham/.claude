"""Direct tests for _lib.hash helpers."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,
                str(Path(__file__).resolve().parents[1] /
                    "skills" / "reindex-memory"))

from _lib import hash as content_hash_mod  # noqa: E402


class ContentHashStable(unittest.TestCase):
    def test_same_inputs_same_hash(self):
        a = content_hash_mod.content_hash("s1", "t", "Read", "/a.py")
        b = content_hash_mod.content_hash("s1", "t", "Read", "/a.py")
        self.assertEqual(a, b)

    def test_different_inputs_different_hash(self):
        a = content_hash_mod.content_hash("s1", "t", "Read", "/a.py")
        b = content_hash_mod.content_hash("s1", "t", "Read", "/b.py")
        self.assertNotEqual(a, b)


class SearchableTextJoinsNonEmpty(unittest.TestCase):
    def test_drops_empty_fields(self):
        self.assertEqual(
            content_hash_mod.searchable_text("Read", "/a.py", ""),
            "Read /a.py")


if __name__ == "__main__":
    unittest.main()
