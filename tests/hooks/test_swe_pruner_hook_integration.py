"""Integration tests for the swe-pruner hook — AC21-AC23.

Full subprocess path: hook reads stdin → swe_pruner.py → writes JSONL.
Tests AC21 (valid payload writes JSONL), AC22 (disabled no JSONL), AC23 (import error exits zero).
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK = _REPO_ROOT / "hooks" / "pre-agent-swe-pruner.sh"

_SITE_PP = ":".join(p for p in sys.path if "site-packages" in p)

_VALID_PAYLOAD = {
    "tool_name": "Agent",
    "tool_input": {
        "subagent_type": "software-engineer",
        "prompt": (
            "## Scratchpad\n"
            "Build the authentication service using TDD.\n"
            "## Protocol\n"
            "The weather today is sunny and warm. Birds are singing.\n"
            "Atmospheric rivers carry moisture from the ocean.\n"
            "Mountain ranges cause orographic lift producing precipitation.\n"
        ),
        "model": "claude-sonnet-4-6",
    },
}


def _run_hook(payload, tmpdir, env=None, session="integration-test"):
    proc_env = {k: v for k, v in os.environ.items()}
    proc_env["CLAUDE_PLUGIN_ROOT"] = str(_REPO_ROOT)
    proc_env["CLAUDE_PLUGIN_DATA"] = tmpdir
    proc_env["HOME"] = tmpdir
    proc_env["CLAUDE_SESSION_ID"] = session
    proc_env["PYTHONPATH"] = ":".join(filter(None, [
        str(_REPO_ROOT / "hooks" / "_lib"),
        _SITE_PP,
        proc_env.get("PYTHONPATH", ""),
    ]))
    proc_env.update(env or {})
    input_str = json.dumps(payload) if isinstance(payload, dict) else str(payload)
    return subprocess.run(
        ["bash", str(HOOK)],
        input=input_str,
        capture_output=True,
        text=True,
        timeout=15,
        env=proc_env,
    )


class TestE2EValidPayloadWritesJsonl(unittest.TestCase):
    """AC21: valid payload writes JSONL with complete fields."""

    def test_e2e_valid_payload_writes_jsonl(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run_hook(_VALID_PAYLOAD, tmpdir)
            self.assertEqual(result.returncode, 0,
                             f"Hook failed: {result.stderr}")
            # Find the JSONL file
            jsonl_files = list(Path(tmpdir).glob("metrics/**/swe-pruner.jsonl"))
            self.assertEqual(len(jsonl_files), 1,
                             f"Expected 1 JSONL file, found: {jsonl_files}")

    def test_e2e_jsonl_record_fields_complete(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run_hook(_VALID_PAYLOAD, tmpdir)
            self.assertEqual(result.returncode, 0)
            jsonl_files = list(Path(tmpdir).glob("metrics/**/swe-pruner.jsonl"))
            self.assertEqual(len(jsonl_files), 1)
            record = json.loads(jsonl_files[0].read_text().strip().splitlines()[0])

            required_fields = [
                "timestamp", "session", "agent_role", "goal_hash",
                "keyword_count", "blocks_analyzed", "total_lines_analyzed",
                "total_proposed_drop_lines", "total_estimated_tokens_saved",
                "prompt_total_chars", "prompt_estimated_tokens",
            ]
            for field in required_fields:
                self.assertIn(field, record, f"Missing field: {field}")

    def test_e2e_jsonl_session_matches_env(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run_hook(_VALID_PAYLOAD, tmpdir, session="my-test-session-123")
            self.assertEqual(result.returncode, 0)
            jsonl_files = list(Path(tmpdir).glob("metrics/**/swe-pruner.jsonl"))
            self.assertTrue(len(jsonl_files) > 0)
            record = json.loads(jsonl_files[0].read_text().strip().splitlines()[0])
            self.assertEqual(record["session"], "my-test-session-123")


class TestE2EDisabledNoJsonl(unittest.TestCase):
    """AC22: when CLAUDE_DISABLE_SWE_PRUNER=1, no JSONL is written."""

    def test_e2e_disabled_no_jsonl_written(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run_hook(
                _VALID_PAYLOAD, tmpdir,
                env={"CLAUDE_DISABLE_SWE_PRUNER": "1"}
            )
            self.assertEqual(result.returncode, 0)
            jsonl_files = list(Path(tmpdir).glob("metrics/**/swe-pruner.jsonl"))
            self.assertEqual(len(jsonl_files), 0,
                             f"JSONL should not be written when disabled, found: {jsonl_files}")


class TestE2EPythonErrorExitsZero(unittest.TestCase):
    """AC23: even if python errors, hook exits zero (graceful degradation)."""

    def test_e2e_python_import_error_exits_zero(self):
        """Simulate python crash by pointing PYTHONPATH to empty dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with tempfile.TemporaryDirectory() as empty_lib:
                proc_env = {k: v for k, v in os.environ.items()}
                proc_env["CLAUDE_PLUGIN_ROOT"] = str(_REPO_ROOT)
                proc_env["CLAUDE_PLUGIN_DATA"] = tmpdir
                proc_env["HOME"] = tmpdir
                proc_env["CLAUDE_SESSION_ID"] = "crash-test"
                # Point to a directory where swe_pruner.py doesn't exist
                proc_env["PYTHONPATH"] = empty_lib
                result = subprocess.run(
                    ["bash", str(HOOK)],
                    input=json.dumps(_VALID_PAYLOAD),
                    capture_output=True, text=True, timeout=15,
                    env=proc_env,
                )
                self.assertEqual(result.returncode, 0,
                                 f"Hook should exit 0 even on python crash, got: "
                                 f"{result.returncode}, stderr: {result.stderr}")
                # stdout must still be empty
                self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
