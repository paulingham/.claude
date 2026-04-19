"""Direct tests for _lib.rows row builder."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,
                str(Path(__file__).resolve().parents[1] /
                    "skills" / "reindex-memory"))

from _lib import rows  # noqa: E402


class RowFromObjFillsDefaults(unittest.TestCase):
    def test_uses_project_from_parent_dir(self):
        fake = Path("/tmp/x/project_hash_x/observations.jsonl")
        row = rows.row_from_obj(
            {"session_id": "s", "timestamp": "t", "tool": "Read"}, fake)
        self.assertEqual(row[2], "project_hash_x")
        self.assertEqual(row[4], "Read")


if __name__ == "__main__":
    unittest.main()
