"""ATDD tests — `hooks/_lib/transcript_usage.py` sum_usage_by_model.

Contract:
- sum_usage_by_model(transcript_path) -> dict[model, dict[field, int]]
  Sums .message.usage.{input_tokens,output_tokens,cache_read_input_tokens,
  cache_creation_input_tokens} grouped by .message.model across ALL
  assistant records in the JSONL transcript.
- Returns {} on missing/empty/garbage input — NEVER raises (fail-open).
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))


def _write_jsonl(path: Path, records: list) -> None:
    lines = [json.dumps(r) for r in records]
    path.write_text("\n".join(lines) + "\n")


class SumUsageByModelHappyPath(unittest.TestCase):
    """AC1 — sums correctly across 2 models from a fixture JSONL."""

    def _run(self, records):
        import transcript_usage
        with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False) as f:
            for r in records:
                f.write(json.dumps(r) + "\n")
            path = f.name
        return transcript_usage.sum_usage_by_model(path)

    def test_sums_two_models_correctly(self):
        records = [
            {
                "type": "assistant",
                "message": {
                    "model": "claude-opus-4-8",
                    "usage": {
                        "input_tokens": 1000,
                        "output_tokens": 200,
                        "cache_read_input_tokens": 500,
                        "cache_creation_input_tokens": 100,
                    },
                },
            },
            {
                "type": "assistant",
                "message": {
                    "model": "claude-sonnet-4-6",
                    "usage": {
                        "input_tokens": 300,
                        "output_tokens": 50,
                        "cache_read_input_tokens": 0,
                        "cache_creation_input_tokens": 0,
                    },
                },
            },
            {
                "type": "assistant",
                "message": {
                    "model": "claude-opus-4-8",
                    "usage": {
                        "input_tokens": 400,
                        "output_tokens": 80,
                        "cache_read_input_tokens": 200,
                        "cache_creation_input_tokens": 50,
                    },
                },
            },
        ]
        result = self._run(records)

        self.assertIn("claude-opus-4-8", result)
        self.assertIn("claude-sonnet-4-6", result)

        opus = result["claude-opus-4-8"]
        self.assertEqual(opus["input_tokens"], 1400)
        self.assertEqual(opus["output_tokens"], 280)
        self.assertEqual(opus["cache_read_input_tokens"], 700)
        self.assertEqual(opus["cache_creation_input_tokens"], 150)

        sonnet = result["claude-sonnet-4-6"]
        self.assertEqual(sonnet["input_tokens"], 300)
        self.assertEqual(sonnet["output_tokens"], 50)

    def test_non_assistant_records_skipped(self):
        records = [
            {
                "type": "user",
                "message": {
                    "model": "claude-opus-4-8",
                    "usage": {"input_tokens": 9999, "output_tokens": 9999},
                },
            },
            {
                "type": "assistant",
                "message": {
                    "model": "claude-opus-4-8",
                    "usage": {"input_tokens": 100, "output_tokens": 20},
                },
            },
        ]
        result = self._run(records)
        self.assertEqual(result["claude-opus-4-8"]["input_tokens"], 100)

    def test_partial_usage_fields_handled(self):
        records = [
            {
                "type": "assistant",
                "message": {
                    "model": "claude-haiku-4-5",
                    "usage": {"input_tokens": 50},
                },
            },
        ]
        result = self._run(records)
        self.assertEqual(result["claude-haiku-4-5"]["input_tokens"], 50)
        self.assertEqual(result["claude-haiku-4-5"]["output_tokens"], 0)


class SumUsageByModelFailOpen(unittest.TestCase):
    """AC2 — missing/empty/garbage input returns {} and NEVER raises."""

    def setUp(self):
        import transcript_usage
        self.fn = transcript_usage.sum_usage_by_model

    def test_missing_file_returns_empty(self):
        result = self.fn("/nonexistent/path/to/transcript.jsonl")
        self.assertEqual(result, {})

    def test_empty_file_returns_empty(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False) as f:
            f.write("")
            path = f.name
        result = self.fn(path)
        self.assertEqual(result, {})

    def test_garbage_lines_return_empty(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False) as f:
            f.write("NOT VALID JSON {\n{{{{{}}}}}}\n")
            path = f.name
        result = self.fn(path)
        self.assertEqual(result, {})

    def test_record_missing_message_usage_skipped(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False) as f:
            f.write(json.dumps({"type": "assistant", "message": {"model": "x"}}) + "\n")
            path = f.name
        result = self.fn(path)
        self.assertEqual(result, {})

    def test_record_missing_model_skipped(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False) as f:
            f.write(json.dumps({
                "type": "assistant",
                "message": {"usage": {"input_tokens": 100}},
            }) + "\n")
            path = f.name
        result = self.fn(path)
        self.assertEqual(result, {})

    def test_none_path_returns_empty(self):
        try:
            result = self.fn(None)
            self.assertEqual(result, {})
        except Exception as e:
            self.fail(f"sum_usage_by_model raised on None path: {e}")


class SumUsageByModelAsScriptEntryPoint(unittest.TestCase):
    """AC2b — module invocable as script: sys.argv[1] path → JSON stdout."""

    def test_invocable_as_script_returns_valid_json(self):
        import subprocess
        records = [
            {
                "type": "assistant",
                "message": {
                    "model": "claude-opus-4-8",
                    "usage": {"input_tokens": 42, "output_tokens": 7},
                },
            }
        ]
        with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False) as f:
            f.write(json.dumps(records[0]) + "\n")
            path = f.name

        result = subprocess.run(
            ["python3", str(REPO_ROOT / "hooks" / "_lib" / "transcript_usage.py"), path],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["claude-opus-4-8"]["input_tokens"], 42)


if __name__ == "__main__":
    unittest.main()
