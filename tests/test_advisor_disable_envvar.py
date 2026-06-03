"""Slice B — pre-agent-advisor.sh honours CLAUDE_DISABLE_ADVISOR_GATE.

Mirrors hooks/pre-agent-allowlist.sh:20 / pre-agent-thinking.sh
reversibility escape. Required precondition for any future Slice C
GREEN-branch flip.

AC-B2: when CLAUDE_DISABLE_ADVISOR_GATE=1, hook exits 0 immediately;
       no resolver subprocess; no advisor-dispatch.jsonl line.
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
HOOK = REPO_ROOT / "hooks" / "pre-agent-advisor.sh"

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
    return base / "metrics" / session / "advisor-dispatch.jsonl"


class DisableEnvVarShortCircuitsAdvisor(unittest.TestCase):
    def setUp(self):
        self.plugin_data = Path(tempfile.mkdtemp(prefix="advisor-disable-"))

    def tearDown(self):
        shutil.rmtree(self.plugin_data, ignore_errors=True)

    def test_disable_env_var_short_circuits_advisor(self):
        session = f"test-advisor-disable-{uuid.uuid4()}"
        log_path = _log_path(session, base=self.plugin_data)
        result = _run_hook(
            {"tool_name": "Agent",
             "tool_input": {"subagent_type": "code-reviewer",
                            "description": "x", "prompt": "y"}},
            env={"CLAUDE_SESSION_ID": session,
                 "CLAUDE_DISABLE_ADVISOR_GATE": "1"},
            plugin_data=self.plugin_data)
        self.assertEqual(result.returncode, 0)
        self.assertFalse(log_path.exists(),
                         "disable env-var should suppress all logging")


if __name__ == "__main__":
    unittest.main()
