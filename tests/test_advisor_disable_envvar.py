"""Slice B — pre-agent-advisor.sh honours CLAUDE_DISABLE_ADVISOR_GATE.

Mirrors hooks/pre-agent-allowlist.sh:20 / pre-agent-thinking.sh
reversibility escape. Required precondition for any future Slice C
GREEN-branch flip.

AC-B2: when CLAUDE_DISABLE_ADVISOR_GATE=1, hook exits 0 immediately;
       no resolver subprocess; no advisor-dispatch.jsonl line.
"""
import json
import os
import subprocess
import unittest
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "hooks" / "pre-agent-advisor.sh"


def _run_hook(payload, env=None):
    proc_env = {**os.environ, **(env or {})}
    return subprocess.run(
        ["bash", str(HOOK)], input=json.dumps(payload),
        capture_output=True, text=True, timeout=10, env=proc_env)


def _log_path(session):
    return Path.home() / ".claude" / "metrics" / session / "advisor-dispatch.jsonl"


def _cleanup(log_path):
    if log_path.exists():
        log_path.unlink()
    if log_path.parent.exists():
        try:
            log_path.parent.rmdir()
        except OSError:
            pass


class DisableEnvVarShortCircuitsAdvisor(unittest.TestCase):
    def test_disable_env_var_short_circuits_advisor(self):
        session = f"test-advisor-disable-{uuid.uuid4()}"
        log_path = _log_path(session)
        try:
            result = _run_hook(
                {"tool_name": "Agent",
                 "tool_input": {"subagent_type": "code-reviewer",
                                "description": "x", "prompt": "y"}},
                env={"CLAUDE_SESSION_ID": session,
                     "CLAUDE_DISABLE_ADVISOR_GATE": "1"})
            self.assertEqual(result.returncode, 0)
            self.assertFalse(log_path.exists(),
                             "disable env-var should suppress all logging")
        finally:
            _cleanup(log_path)


if __name__ == "__main__":
    unittest.main()
