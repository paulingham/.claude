"""Cycle 20: subagent-validation.sh registration must survive wave2-F1.

The wave2-F1 spec explicitly forbids touching subagent-validation.sh — it
already does post-hoc subagent quality validation on SubagentStop. Adding
the allowlist hook on PreToolUse Agent must NOT displace, replace, or
re-order it. This test pins the SubagentStop registration so any future
edit of settings.json that breaks subagent-validation.sh fails CI.

Match is by hook script basename so the assertion survives the
$HOME/CLAUDE_CONFIG_DIR portability migration (settings.json no longer
hard-codes literal paths — see rules/_detail/agent-protocol.md
§ Portable Config Dir).
"""
import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class SubagentValidationStillRegistered(unittest.TestCase):
    def test_subagent_validation_hook_present_on_subagent_stop(self):
        scripts = self._subagent_stop_scripts()
        self.assertIn("subagent-validation.sh", scripts)

    def test_subagent_validation_hook_runs_first(self):
        # Position matters — validation runs BEFORE trajectory + cwd checks
        # so its findings can surface in the trajectory record.
        scripts = self._subagent_stop_scripts()
        self.assertEqual(scripts[0], "subagent-validation.sh",
                         "subagent-validation.sh must be the first SubagentStop hook")

    def _subagent_stop_scripts(self):
        settings = json.loads((REPO_ROOT / "settings.json").read_text())
        groups = settings["hooks"]["SubagentStop"]
        # First group is the bash hook batch; second is the hcom poll
        first = groups[0]
        return [self._basename(h["command"])
                for h in first["hooks"] if h["type"] == "command"]

    @staticmethod
    def _basename(command):
        match = re.search(r"hooks/([A-Za-z0-9_.-]+\.sh)", command)
        return match.group(1) if match else command
