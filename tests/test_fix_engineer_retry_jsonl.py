"""Unit test: fix_engineer_retry_log.emit_retry_record schema (AC6).

Imports use the flat sys.path pattern established in conftest.py and
test_jsonl_append.py — hooks/_lib has no __init__.py and is not a package.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))

from fix_engineer_retry_log import emit_retry_record  # noqa: E402

REQUIRED_KEYS = {
    "task_id",
    "round_idx",
    "model_tier_before",
    "model_tier_after",
    "verdict",
    "finding_count",
}


class TestEmitRetryRecordSchema(unittest.TestCase):

    def setUp(self):
        self.metrics_dir = tempfile.mkdtemp(prefix="retry-log-")

    def test_emit_retry_record_schema(self):
        """All 6 required schema keys must be present in the written JSONL line."""
        emit_retry_record(
            metrics_dir=self.metrics_dir,
            task_id="c2-fanout-cap-audit",
            round_idx=3,
            model_tier_before="opus",
            model_tier_after="sonnet",
            verdict="CHANGES_REQUESTED",
            finding_count=2,
        )
        jsonl_path = Path(self.metrics_dir) / "fix-engineer-retry.jsonl"
        self.assertTrue(jsonl_path.exists(), "fix-engineer-retry.jsonl not created")
        line = jsonl_path.read_text(encoding="utf-8").strip()
        record = json.loads(line)
        missing = REQUIRED_KEYS - record.keys()
        self.assertFalse(missing, f"Missing schema keys: {missing}")

    def test_emit_retry_record_values(self):
        """Values written to JSONL must match the inputs exactly."""
        emit_retry_record(
            metrics_dir=self.metrics_dir,
            task_id="test-task",
            round_idx=1,
            model_tier_before="sonnet",
            model_tier_after="sonnet",
            verdict="APPROVE",
            finding_count=0,
        )
        jsonl_path = Path(self.metrics_dir) / "fix-engineer-retry.jsonl"
        record = json.loads(jsonl_path.read_text(encoding="utf-8").strip())
        self.assertEqual(record["task_id"], "test-task")
        self.assertEqual(record["round_idx"], 1)
        self.assertEqual(record["model_tier_before"], "sonnet")
        self.assertEqual(record["model_tier_after"], "sonnet")
        self.assertEqual(record["verdict"], "APPROVE")
        self.assertEqual(record["finding_count"], 0)


if __name__ == "__main__":
    unittest.main()
