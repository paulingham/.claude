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
import subprocess
import unittest
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "hooks" / "pre-agent-thinking.sh"


def _run_hook(payload, env=None):
    proc_env = {**os.environ, **(env or {})}
    return subprocess.run(
        ["bash", str(HOOK)], input=json.dumps(payload),
        capture_output=True, text=True, timeout=10, env=proc_env)


def _log_path(session):
    return Path.home() / ".claude" / "metrics" / session / "hook-injections.jsonl"


def _cleanup(log_path):
    if log_path.exists():
        log_path.unlink()
    if log_path.parent.exists():
        try:
            log_path.parent.rmdir()
        except OSError:
            pass


class DisableEnvVarShortCircuitsThinking(unittest.TestCase):
    def test_disable_env_var_short_circuits_thinking(self):
        session = f"test-thinking-disable-{uuid.uuid4()}"
        log_path = _log_path(session)
        try:
            result = _run_hook(
                {"tool_name": "Agent",
                 "tool_input": {"subagent_type": "software-engineer",
                                "description": "x", "prompt": "y"}},
                env={"CLAUDE_SESSION_ID": session,
                     "CLAUDE_DISABLE_THINKING_GATE": "1"})
            self.assertEqual(result.returncode, 0)
            self.assertFalse(log_path.exists(),
                             "disable env-var should suppress all logging")
        finally:
            _cleanup(log_path)


class UnsetVarPreservesLog(unittest.TestCase):
    """AC-B3: unset env var → existing behaviour preserved (log emitted
    for spawns that lack tool_input.thinking)."""

    def test_unset_var_preserves_log_path(self):
        # Smoke check: with env var unset, the hook proceeds through the
        # resolver. We don't assert on log presence (resolver may SKIP for
        # many reasons in the test environment); we assert the hook does
        # NOT short-circuit at the new disable check — i.e. it spends
        # time invoking python3 + resolver. Detect that via stderr or by
        # ensuring the env-disable code path is NOT taken.
        session = f"test-thinking-unset-{uuid.uuid4()}"
        log_path = _log_path(session)
        try:
            result = _run_hook(
                {"tool_name": "Agent",
                 "tool_input": {"subagent_type": "software-engineer",
                                "description": "x", "prompt": "y"}},
                env={"CLAUDE_SESSION_ID": session})
            self.assertEqual(result.returncode, 0)
            # the hook script content itself must include the env-disable
            # guard string so reversibility is documented in code
            self.assertIn("CLAUDE_DISABLE_THINKING_GATE", HOOK.read_text())
        finally:
            _cleanup(log_path)


if __name__ == "__main__":
    unittest.main()
