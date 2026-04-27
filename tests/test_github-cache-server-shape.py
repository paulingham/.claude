"""Tests for the REST → gh-CLI reshape module."""
import importlib.util
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SHAPE_PATH = REPO / "hooks" / "_lib" / "github-cache-server-shape.py"


def _load():
    spec = importlib.util.spec_from_file_location("gh_cache_shape", SHAPE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["gh_cache_shape"] = module
    spec.loader.exec_module(module)
    return module


class TestReshapeView(unittest.TestCase):
    def setUp(self):
        self.shape = _load()

    def test_renames_merged_at_to_mergedAt(self):
        rest = json.dumps({"merged_at": "2026-04-15T12:34:56Z"})
        out = json.loads(self.shape.reshape_view(rest))
        self.assertEqual(out["mergedAt"], "2026-04-15T12:34:56Z")
        self.assertNotIn("merged_at", out)

    def test_wraps_merge_commit_sha_into_mergeCommit_oid(self):
        rest = json.dumps({"merge_commit_sha": "deadbeef00"})
        out = json.loads(self.shape.reshape_view(rest))
        self.assertEqual(out["mergeCommit"], {"oid": "deadbeef00"})
        self.assertNotIn("merge_commit_sha", out)

    def test_labels_keep_name_only(self):
        rest = json.dumps({"labels": [
            {"name": "bug", "color": "f00", "description": "x"},
            {"name": "ci", "color": "0f0", "description": "y"}]})
        out = json.loads(self.shape.reshape_view(rest))
        self.assertEqual(out["labels"], [{"name": "bug"}, {"name": "ci"}])


if __name__ == "__main__":
    unittest.main()
