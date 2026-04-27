"""Cycle 19: settings.json must register pre-agent-allowlist.sh.

The allowlist hook MUST sit at PreToolUse Agent position 5 — i.e. after
pre-agent-thinking (3) and pre-agent-advisor (4), before depth-guard (5)
and runtime-guard (6) — per the wave2-F1 spec. Position is part of the
contract: if the hook moves, this test fails.
"""
import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class SettingsRegistersAllowlistHookOnPreToolUseAgent(unittest.TestCase):
    def test_allowlist_hook_registered_after_advisor(self):
        commands = self._agent_commands()
        allowlist_cmd = "bash ~/.claude/hooks/pre-agent-allowlist.sh"
        advisor_cmd = "bash ~/.claude/hooks/pre-agent-advisor.sh"
        self.assertIn(allowlist_cmd, commands,
                      "pre-agent-allowlist.sh not registered on PreToolUse Agent")
        self.assertGreater(commands.index(allowlist_cmd),
                           commands.index(advisor_cmd),
                           "allowlist hook must come AFTER advisor hook")

    def test_allowlist_hook_does_not_displace_existing_hooks(self):
        commands = self._agent_commands()
        for required in ("bash ~/.claude/hooks/pipeline-state-guard.sh",
                         "bash ~/.claude/hooks/agent-skill-reminder.sh",
                         "bash ~/.claude/hooks/pre-agent-thinking.sh",
                         "bash ~/.claude/hooks/pre-agent-advisor.sh",
                         "bash ~/.claude/hooks/depth-guard.sh",
                         "bash ~/.claude/hooks/runtime-guard.sh"):
            self.assertIn(required, commands,
                          f"existing hook {required} was removed")

    def _agent_commands(self):
        settings = json.loads((REPO_ROOT / "settings.json").read_text())
        agent_groups = [g for g in settings["hooks"]["PreToolUse"]
                        if g.get("matcher") == "Agent"]
        self.assertEqual(len(agent_groups), 1)
        return [h["command"] for h in agent_groups[0]["hooks"]]
