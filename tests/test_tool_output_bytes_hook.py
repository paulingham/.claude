"""Tool output-bytes telemetry — A2 hook test.

Pins the contract for hooks/tool-output-bytes.sh:
- PostToolUse / PostToolUseFailure → one JSONL line per tool call to
  metrics/{session}/tool-output-bytes.jsonl with fields ts, tool, char_count,
  estimated_tokens, agent_role (opt), task_id (opt).
- estimated_tokens = char_count // 4 (truncated int).
- Threshold warning to stderr when estimated_tokens > 20000.
- Non-string tool_response.output → char_count: 0 with reason "non-string-output".
- CLAUDE_DISABLE_TOOL_OUTPUT_BYTES=1 fast-exits.
"""
import json
import os
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "hooks" / "tool-output-bytes.sh"


def _payload(tool="Bash", output="hello", subagent_type=None,
             hook_event_name="PostToolUse"):
    payload = {
        "hook_event_name": hook_event_name,
        "tool_name": tool,
        "tool_response": {"output": output},
    }
    if subagent_type is not None:
        payload["tool_input"] = {"subagent_type": subagent_type}
    return payload


def _run_hook(payload, env_extra=None):
    env = {**os.environ}
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        ["bash", str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
    )


def _read_lines(metrics_dir, session_id):
    p = Path(metrics_dir) / session_id / "tool-output-bytes.jsonl"
    if not p.exists():
        return []
    return [line for line in p.read_text().splitlines() if line.strip()]


class TestToolOutputBytesHook(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="tob-"))
        self.session = f"tob-{uuid.uuid4().hex[:8]}"
        self.env = {
            "CLAUDE_SESSION_ID": self.session,
            "CLAUDE_HOOK_LOG_DIR": str(self.tmp),
            "HOME": str(self.tmp),
        }

    def _run(self, payload, **extra):
        env = {**self.env, **extra}
        return _run_hook(payload, env_extra=env)

    def test_large_output_writes_record_and_emits_stderr_warning(self):
        """100k-char output → estimated_tokens > 20000, JSONL line, stderr warn."""
        big = "x" * 100_000
        payload = _payload(tool="Bash", output=big,
                           subagent_type="software-engineer")
        proc = self._run(payload)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = _read_lines(self.tmp, self.session)
        self.assertEqual(len(lines), 1, f"expected 1 line, got {lines}")
        rec = json.loads(lines[0])
        self.assertEqual(rec["tool"], "Bash")
        self.assertEqual(rec["char_count"], 100_000)
        self.assertGreater(rec["estimated_tokens"], 20_000)
        self.assertEqual(rec["estimated_tokens"], 100_000 // 4)
        self.assertEqual(rec["agent_role"], "software-engineer")
        self.assertIn("ts", rec)
        self.assertTrue(proc.stderr.strip(),
                        "expected stderr warning for large output")

    def test_small_output_writes_record_no_stderr_warning(self):
        """100-char output → JSONL line, NO stderr warning."""
        payload = _payload(tool="Bash", output="x" * 100)
        proc = self._run(payload)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = _read_lines(self.tmp, self.session)
        self.assertEqual(len(lines), 1)
        rec = json.loads(lines[0])
        self.assertEqual(rec["char_count"], 100)
        self.assertEqual(rec["estimated_tokens"], 25)
        self.assertEqual(proc.stderr.strip(), "",
                         f"expected no stderr warning, got: {proc.stderr!r}")

    def test_non_string_output_records_zero_with_reason(self):
        """Non-string output (e.g. list/dict) → char_count: 0, reason set."""
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Read",
            "tool_response": {"output": {"nested": "object"}},
        }
        proc = self._run(payload)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = _read_lines(self.tmp, self.session)
        self.assertEqual(len(lines), 1)
        rec = json.loads(lines[0])
        self.assertEqual(rec["char_count"], 0)
        self.assertEqual(rec["reason"], "non-string-output")

    def test_disable_env_var_fast_exits(self):
        """CLAUDE_DISABLE_TOOL_OUTPUT_BYTES=1 → no JSONL line written."""
        payload = _payload(output="x" * 100_000)
        proc = self._run(payload, CLAUDE_DISABLE_TOOL_OUTPUT_BYTES="1")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = _read_lines(self.tmp, self.session)
        self.assertEqual(lines, [])

    def test_missing_tool_response_skips_silently(self):
        """No tool_response → exit 0, no line."""
        payload = {"hook_event_name": "PostToolUse", "tool_name": "Bash"}
        proc = self._run(payload)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = _read_lines(self.tmp, self.session)
        self.assertEqual(lines, [])

    def test_task_id_recorded_when_env_set(self):
        """CLAUDE_PIPELINE_TASK_ID populates task_id field."""
        payload = _payload(output="hi")
        proc = self._run(payload, CLAUDE_PIPELINE_TASK_ID="my-task")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = _read_lines(self.tmp, self.session)
        self.assertEqual(len(lines), 1)
        rec = json.loads(lines[0])
        self.assertEqual(rec["task_id"], "my-task")


if __name__ == "__main__":
    unittest.main()
