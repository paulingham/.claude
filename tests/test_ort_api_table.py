"""Slice 0+2: IDX snapshot fixture — locks 1.24.4 ORT indices.

Not env-gated: runs on every machine. Breaks loudly on ORT version bump.
"""
import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_FIXTURE = REPO_ROOT / "skills" / "embedder" / "tests" / "fixtures" \
    / "ort_api_indices.json"


class OrtApiIndicesFixture(unittest.TestCase):
    def test_fixture_exists_and_has_24_names(self):
        self.assertTrue(_FIXTURE.exists(), f"missing {_FIXTURE}")
        data = json.loads(_FIXTURE.read_text())
        self.assertGreaterEqual(len(data["idx"]), 24)
        self.assertEqual(data["ort_version"], "1.24.4")


if __name__ == "__main__":
    unittest.main()
