"""Slice 3: settings.json must register instinct-injector.sh at position 6.

The instinct-injector hook MUST sit at PreToolUse Agent index 5 (position 6),
i.e. AFTER pre-agent-allowlist (index 4) and BEFORE depth-guard (index 6,
shifted from 5) and runtime-guard (index 7, shifted from 6). Position is part
of the contract: decision hooks (thinking, advisor, allowlist, instinct)
cluster contiguously before resource-cap guards (depth, runtime). If the hook
moves, this test fails.
"""
import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_ORDER = [
    "bash ~/.claude/hooks/pipeline-state-guard.sh",
    "bash ~/.claude/hooks/agent-skill-reminder.sh",
    "bash ~/.claude/hooks/pre-agent-thinking.sh",
    "bash ~/.claude/hooks/pre-agent-advisor.sh",
    "bash ~/.claude/hooks/pre-agent-allowlist.sh",
    "bash ~/.claude/hooks/instinct-injector.sh",
    "bash ~/.claude/hooks/depth-guard.sh",
    "bash ~/.claude/hooks/runtime-guard.sh",
]


class SettingsRegistersInstinctInjectorAtPosition6(unittest.TestCase):
    def test_instinct_injector_registered_at_index_5(self):
        commands = self._agent_commands()
        injector = "bash ~/.claude/hooks/instinct-injector.sh"
        self.assertIn(injector, commands,
                      "instinct-injector.sh not registered on PreToolUse Agent")
        self.assertEqual(commands.index(injector), 5,
                         "instinct-injector.sh must be at index 5 (position 6)")

    def test_full_pretoolse_agent_hook_order_matches_snapshot(self):
        self.assertEqual(self._agent_commands(), EXPECTED_ORDER)

    def test_instinct_injector_sits_after_allowlist_before_depth_guard(self):
        commands = self._agent_commands()
        injector_idx = commands.index("bash ~/.claude/hooks/instinct-injector.sh")
        allowlist_idx = commands.index("bash ~/.claude/hooks/pre-agent-allowlist.sh")
        depth_idx = commands.index("bash ~/.claude/hooks/depth-guard.sh")
        self.assertGreater(injector_idx, allowlist_idx)
        self.assertLess(injector_idx, depth_idx)

    def _agent_commands(self):
        settings = json.loads((REPO_ROOT / "settings.json").read_text())
        agent_groups = [g for g in settings["hooks"]["PreToolUse"]
                        if g.get("matcher") == "Agent"]
        self.assertEqual(len(agent_groups), 1)
        return [h["command"] for h in agent_groups[0]["hooks"]]
