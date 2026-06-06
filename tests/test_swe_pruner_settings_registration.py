"""Tests for settings.json registration of swe-pruner hook — AC10, AC11.

Verifies the hook is registered in the Agent matcher, uses the fail-safe
pattern, and is positioned after scratchpad-bytes hook.
"""
import json
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SETTINGS = _REPO_ROOT / "settings.json"


def _load_settings():
    return json.loads(_SETTINGS.read_text())


def _find_agent_hooks(settings):
    """Return the hooks list for the 'Agent' matcher."""
    for group in settings.get("hooks", {}).get("PreToolUse", []):
        if group.get("matcher") == "Agent":
            return group.get("hooks", [])
    return []


def _hook_command_string(hook_entry):
    """Extract the command string from a hook entry."""
    args = hook_entry.get("args", [])
    for arg in args:
        if isinstance(arg, str) and "pre-agent-swe-pruner" in arg:
            return arg
    return ""


class TestSettingsRegistration(unittest.TestCase):
    """AC10: settings.json contains swe-pruner hook in Agent PreToolUse."""

    def test_settings_agent_hooks_contains_swe_pruner(self):
        settings = _load_settings()
        agent_hooks = _find_agent_hooks(settings)
        hook_commands = [str(h) for h in agent_hooks]
        found = any("pre-agent-swe-pruner" in str(h) for h in agent_hooks)
        self.assertTrue(found,
                        "pre-agent-swe-pruner.sh not found in Agent PreToolUse hooks")

    def test_settings_swe_pruner_uses_failsafe_pattern(self):
        """Hook must use: h="...hooks/pre-agent-swe-pruner.sh"; [ -x "$h" ] && exec "$h" || exit 0"""
        settings = _load_settings()
        agent_hooks = _find_agent_hooks(settings)
        for hook in agent_hooks:
            args = hook.get("args", [])
            for arg in args:
                if isinstance(arg, str) and "pre-agent-swe-pruner" in arg:
                    # Must have the fail-safe pattern
                    self.assertIn('[ -x "$h" ]', arg,
                                  "Hook missing fail-safe [ -x \"$h\" ] check")
                    self.assertIn("exec", arg,
                                  "Hook missing 'exec' in fail-safe pattern")
                    self.assertIn("exit 0", arg,
                                  "Hook missing 'exit 0' fallback in fail-safe pattern")
                    return
        self.fail("Could not find pre-agent-swe-pruner.sh hook entry to verify fail-safe pattern")


class TestSettingsHookPosition(unittest.TestCase):
    """AC11: swe-pruner hook is after scratchpad-bytes hook."""

    def test_settings_swe_pruner_after_scratchpad_bytes(self):
        settings = _load_settings()
        agent_hooks = _find_agent_hooks(settings)
        scratchpad_idx = None
        swe_pruner_idx = None
        for i, hook in enumerate(agent_hooks):
            args_str = str(hook.get("args", []))
            if "scratchpad-bytes" in args_str:
                scratchpad_idx = i
            if "pre-agent-swe-pruner" in args_str:
                swe_pruner_idx = i

        self.assertIsNotNone(scratchpad_idx,
                             "scratchpad-bytes hook not found in Agent hooks")
        self.assertIsNotNone(swe_pruner_idx,
                             "pre-agent-swe-pruner hook not found in Agent hooks")
        self.assertGreater(swe_pruner_idx, scratchpad_idx,
                           f"swe-pruner (idx={swe_pruner_idx}) must come AFTER "
                           f"scratchpad-bytes (idx={scratchpad_idx})")


if __name__ == "__main__":
    unittest.main()
