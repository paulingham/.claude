"""Cycle 20: subagent-validation.sh registration must survive wave2-F1.

The wave2-F1 spec explicitly forbids touching subagent-validation.sh — it
already does post-hoc subagent quality validation on SubagentStop. Adding
the allowlist hook on PreToolUse Agent must NOT displace, replace, or
re-order it. This test pins the SubagentStop registration so any future
edit of settings.json that breaks subagent-validation.sh fails CI.
"""
import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class SubagentValidationStillRegistered(unittest.TestCase):
    def test_subagent_validation_hook_present_on_subagent_stop(self):
        commands = self._subagent_stop_commands()
        self.assertIn("bash ~/.claude/hooks/subagent-validation.sh", commands)

    def test_subagent_validation_hook_runs_first(self):
        # Position matters — validation runs BEFORE trajectory + cwd checks
        # so its findings can surface in the trajectory record.
        commands = self._subagent_stop_commands()
        idx = commands.index("bash ~/.claude/hooks/subagent-validation.sh")
        self.assertEqual(idx, 0,
                         "subagent-validation.sh must be the first SubagentStop hook")

    def _subagent_stop_commands(self):
        settings = json.loads((REPO_ROOT / "settings.json").read_text())
        groups = settings["hooks"]["SubagentStop"]
        # First group is the bash hook batch; second is the hcom poll
        first = groups[0]
        return [h["command"] for h in first["hooks"] if h["type"] == "command"]
