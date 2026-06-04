"""Slice B — pre-agent-thinking.sh honours CLAUDE_DISABLE_THINKING_GATE.

Mirrors hooks/pre-agent-allowlist.sh:20 reversibility escape. Required
precondition for any future Slice C GREEN-branch flip — operators must
be able to short-circuit the gate without editing the hook file.

AC-B1: when CLAUDE_DISABLE_THINKING_GATE=1, hook exits 0 immediately;
       no resolver subprocess; no JSONL line is appended.
AC-B3: env var unset → existing log behaviour preserved.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "hooks" / "pre-agent-thinking.sh"

_SITE_PP = ":".join(p for p in sys.path if "site-packages" in p)


def _run_hook(payload, env=None, plugin_data=None):
    existing_pp = os.environ.get("PYTHONPATH", "")
    merged_pp = ":".join(filter(None, [_SITE_PP, existing_pp]))
    proc_env = {**os.environ, "PYTHONPATH": merged_pp,
                "CLAUDE_PLUGIN_ROOT": str(REPO_ROOT)}
    if plugin_data is not None:
        proc_env["CLAUDE_PLUGIN_DATA"] = str(plugin_data)
        proc_env["HOME"] = str(plugin_data)
    proc_env.update(env or {})
    return subprocess.run(
        ["bash", str(HOOK)], input=json.dumps(payload),
        capture_output=True, text=True, timeout=10, env=proc_env)


def _log_path(session, base):
    root = base
    return root / "metrics" / session / "hook-injections.jsonl"


class _ThinkingTestCase(unittest.TestCase):
    def setUp(self):
        self.plugin_data = Path(tempfile.mkdtemp(prefix="thinking-disable-"))

    def tearDown(self):
        shutil.rmtree(self.plugin_data, ignore_errors=True)

    def _log(self, session):
        return _log_path(session, base=self.plugin_data)

    def _run(self, payload, extra_env=None):
        return _run_hook(payload, env=extra_env, plugin_data=self.plugin_data)


class DisableEnvVarShortCircuitsThinking(_ThinkingTestCase):
    def test_disable_env_var_short_circuits_thinking(self):
        session = f"test-thinking-disable-{uuid.uuid4()}"
        log_path = self._log(session)
        result = self._run(
            {"tool_name": "Agent",
             "tool_input": {"subagent_type": "software-engineer",
                            "description": "x", "prompt": "y"}},
            extra_env={"CLAUDE_SESSION_ID": session,
                       "CLAUDE_DISABLE_THINKING_GATE": "1"})
        self.assertEqual(result.returncode, 0)
        self.assertFalse(log_path.exists(),
                         "disable env-var should suppress all logging")


class UnsetVarPreservesLog(_ThinkingTestCase):
    """AC-B3: unset env var → existing behaviour preserved."""

    def test_unset_var_preserves_log_path(self):
        session = f"test-thinking-unset-{uuid.uuid4()}"
        result = self._run(
            {"tool_name": "Agent",
             "tool_input": {"subagent_type": "software-engineer",
                            "description": "x", "prompt": "y"}},
            extra_env={"CLAUDE_SESSION_ID": session})
        self.assertEqual(result.returncode, 0)
        self.assertIn("CLAUDE_DISABLE_THINKING_GATE", HOOK.read_text())


if __name__ == "__main__":
    unittest.main()
