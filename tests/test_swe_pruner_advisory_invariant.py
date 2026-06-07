"""Tests for the advisory invariant — AC9, AC7, AC8.

INVARIANT 1: The hook NEVER emits modified_tool_input (advisory mode).
stdout must be empty. exit code must always be 0.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = _REPO_ROOT / "hooks" / "pre-agent-swe-pruner.sh"

_SITE_PP = ":".join(p for p in sys.path if "site-packages" in p)


def _run_hook(payload, env=None):
    proc_env = {k: v for k, v in os.environ.items()}
    proc_env["CLAUDE_PLUGIN_ROOT"] = str(_REPO_ROOT)
    proc_env["CLAUDE_PLUGIN_DATA"] = tempfile.mkdtemp(prefix="swe-pruner-test-")
    proc_env["HOME"] = proc_env["CLAUDE_PLUGIN_DATA"]
    proc_env["PYTHONPATH"] = ":".join(filter(None, [
        str(_REPO_ROOT / "hooks" / "_lib"),
        _SITE_PP,
        proc_env.get("PYTHONPATH", ""),
    ]))
    proc_env.update(env or {})
    input_str = json.dumps(payload) if isinstance(payload, dict) else payload
    return subprocess.run(
        ["bash", str(HOOK)],
        input=input_str,
        capture_output=True,
        text=True,
        timeout=15,
        env=proc_env,
    )


_VALID_PAYLOAD = {
    "tool_name": "Agent",
    "tool_input": {
        "subagent_type": "software-engineer",
        "prompt": "## Scratchpad\nBuild the authentication service.\n## Protocol\nSome protocol content about things unrelated to authentication.\n",
        "model": "claude-sonnet-4-6",
    },
}


class TestHookExitsZero(unittest.TestCase):
    """AC7: hook reads stdin and exits zero."""

    def test_hook_reads_stdin_and_exits_zero(self):
        result = _run_hook(_VALID_PAYLOAD)
        self.assertEqual(result.returncode, 0,
                         f"Hook exited non-zero: {result.stderr}")

    def test_hook_respects_disable_envvar(self):
        result = _run_hook(_VALID_PAYLOAD, env={"CLAUDE_DISABLE_SWE_PRUNER": "1"})
        self.assertEqual(result.returncode, 0)


class TestHookGracefulDegradation(unittest.TestCase):
    """AC8: hook exits zero on malformed JSON, empty stdin, python crash."""

    def test_hook_exits_zero_on_malformed_json(self):
        result = _run_hook("this is not json at all {broken}")
        self.assertEqual(result.returncode, 0)

    def test_hook_exits_zero_on_empty_stdin(self):
        result = _run_hook("")
        self.assertEqual(result.returncode, 0)

    def test_hook_exits_zero_on_missing_tool_input(self):
        result = _run_hook({"tool_name": "Agent"})
        self.assertEqual(result.returncode, 0)


class TestHookStdoutEmpty(unittest.TestCase):
    """AC9: INVARIANT 1 — hook stdout MUST be empty (no modified_tool_input)."""

    def test_hook_stdout_is_empty(self):
        result = _run_hook(_VALID_PAYLOAD)
        self.assertEqual(result.stdout, "",
                         f"Hook emitted to stdout (INVARIANT VIOLATION): {result.stdout!r}")

    def test_no_modified_tool_input_in_stdout(self):
        result = _run_hook(_VALID_PAYLOAD)
        # modified_tool_input must NOT appear in stdout
        self.assertNotIn("modified_tool_input", result.stdout)

    def test_stdout_empty_on_malformed_input(self):
        result = _run_hook("not json")
        self.assertEqual(result.stdout, "")

    def test_stdout_empty_when_disabled(self):
        result = _run_hook(_VALID_PAYLOAD, env={"CLAUDE_DISABLE_SWE_PRUNER": "1"})
        self.assertEqual(result.stdout, "")

    def test_stdout_empty_on_empty_stdin(self):
        result = _run_hook("")
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
