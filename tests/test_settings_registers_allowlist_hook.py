"""Cycle 19: settings.json must register pre-agent-allowlist.sh.

The allowlist hook MUST sit at PreToolUse Agent index 4, AFTER pre-agent-thinking
(2) and pre-agent-advisor (3), BEFORE instinct-injector (5),
verification-freshness-guard (6), scratchpad-bytes (7), depth-guard (8), and
runtime-guard (9). Position is part of the contract: if the hook moves, this
test fails.

Hook identity is parsed from `args[-1]` (the literal exec command string);
`h["command"]` is always "bash" because the harness wraps every hook in
`bash -lc 'exec ...'`.
"""
import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _hook_basenames():
    settings = json.loads((REPO_ROOT / "settings.json").read_text())
    agent_groups = [g for g in settings["hooks"]["PreToolUse"]
                    if g.get("matcher") == "Agent"]
    assert len(agent_groups) == 1
    out = []
    for h in agent_groups[0]["hooks"]:
        args = h.get("args", [])
        text = args[-1] if args else ""
        if "/hooks/" in text and ".sh" in text:
            out.append(text.split("/hooks/")[-1].split(".sh")[0])
    return out


class SettingsRegistersAllowlistHookOnPreToolUseAgent(unittest.TestCase):
    def test_allowlist_hook_registered_after_advisor(self):
        names = _hook_basenames()
        self.assertIn("pre-agent-allowlist", names,
                      "pre-agent-allowlist.sh not registered on PreToolUse Agent")
        self.assertGreater(names.index("pre-agent-allowlist"),
                           names.index("pre-agent-advisor"),
                           "allowlist hook must come AFTER advisor hook")

    def test_allowlist_hook_does_not_displace_existing_hooks(self):
        names = _hook_basenames()
        for required in ("pipeline-state-guard", "agent-skill-reminder",
                         "pre-agent-thinking", "pre-agent-advisor",
                         "depth-guard", "runtime-guard"):
            self.assertIn(required, names,
                          f"existing hook {required} was removed")
