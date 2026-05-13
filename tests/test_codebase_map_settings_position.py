"""AC22-bis: settings.json SessionStart hook position pin.

The codebase-map-rebuild.sh hook MUST land between metrics-gc.sh and
hook-self-test.sh in the SessionStart hooks array. This is a contract
because:

- AFTER metrics-gc.sh: metrics-gc trims old metrics dirs first, freeing
  space before codebase-map-rebuild.sh emits its forensic JSONL line.
- BEFORE hook-self-test.sh: a self-test failure must not mask the
  rebuild having run successfully.

Pinned by `pipeline-state/auto-codebase-map/plan.md` § Slice C AC22-bis.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _effective_command_line(hook: dict) -> str:
    """Reconstruct an effective shell command line from a hook entry.

    v2.1.139 split string-form `bash foo.sh` into exec-form
    `command=bash`, `args=[foo.sh]`. Tests that substring-match on the
    script basename must inspect both fields. Returns "" for non-command
    typed entries (mcp_tool, agent).
    """
    if hook.get("type") != "command":
        return ""
    cmd = hook.get("command", "")
    args = hook.get("args", []) or []
    return " ".join([cmd, *args]).strip()


class SettingsJsonHookPositionPinned(unittest.TestCase):
    """The SessionStart hooks array contains the rebuild hook in pinned slot."""

    def setUp(self):
        settings = json.loads((REPO_ROOT / "settings.json").read_text())
        # SessionStart has multiple groups (no matcher, matcher=compact, etc).
        # We want the no-matcher group that holds the harness hooks.
        self.session_start_groups = settings["hooks"]["SessionStart"]
        # Find the group with no matcher key (harness lifecycle hooks).
        self.harness_group = None
        for group in self.session_start_groups:
            if "matcher" not in group:
                # The first no-matcher group is the harness lifecycle group
                # (it carries the multiple hooks, not the hcom one-liner).
                if len(group.get("hooks", [])) > 1:
                    self.harness_group = group
                    break
        self.assertIsNotNone(
            self.harness_group,
            "could not locate SessionStart harness hook group",
        )

    def _commands(self):
        # v2.1.139 exec-form: command is the binary, args carries the script path.
        # Reconstruct the effective command line so substring assertions still
        # work whether settings.json uses string-form or exec-form.
        return [_effective_command_line(h) for h in self.harness_group["hooks"]]

    def test_codebase_map_rebuild_registered(self):
        commands = self._commands()
        joined = " ".join(commands)
        self.assertIn(
            "codebase-map-rebuild.sh",
            joined,
            "codebase-map-rebuild.sh not registered in SessionStart hooks",
        )

    def test_codebase_map_rebuild_after_metrics_gc(self):
        commands = self._commands()
        gc_idx = self._find_index(commands, "metrics-gc.sh")
        rebuild_idx = self._find_index(commands, "codebase-map-rebuild.sh")
        self.assertGreater(
            rebuild_idx,
            gc_idx,
            "codebase-map-rebuild.sh must run AFTER metrics-gc.sh",
        )

    def test_codebase_map_rebuild_before_hook_self_test(self):
        commands = self._commands()
        rebuild_idx = self._find_index(commands, "codebase-map-rebuild.sh")
        self_test_idx = self._find_index(commands, "hook-self-test.sh")
        self.assertLess(
            rebuild_idx,
            self_test_idx,
            "codebase-map-rebuild.sh must run BEFORE hook-self-test.sh",
        )

    def test_position_immediately_between_metrics_gc_and_hook_self_test(self):
        """Strict adjacency: metrics-gc, codebase-map-rebuild, hook-self-test."""
        commands = self._commands()
        gc_idx = self._find_index(commands, "metrics-gc.sh")
        rebuild_idx = self._find_index(commands, "codebase-map-rebuild.sh")
        self_test_idx = self._find_index(commands, "hook-self-test.sh")
        self.assertEqual(
            rebuild_idx,
            gc_idx + 1,
            "codebase-map-rebuild.sh must immediately follow metrics-gc.sh",
        )
        self.assertEqual(
            self_test_idx,
            rebuild_idx + 1,
            "hook-self-test.sh must immediately follow codebase-map-rebuild.sh",
        )

    @staticmethod
    def _find_index(commands, fragment):
        for idx, cmd in enumerate(commands):
            if fragment in cmd:
                return idx
        raise AssertionError(f"{fragment} not found in commands")


class SettingsJsonStopHookRegistered(unittest.TestCase):
    """codebase-map-poll.sh registered on Stop trigger."""

    def setUp(self):
        settings = json.loads((REPO_ROOT / "settings.json").read_text())
        self.stop_groups = settings["hooks"]["Stop"]

    def test_poll_hook_registered(self):
        all_commands = []
        for group in self.stop_groups:
            for hook in group.get("hooks", []):
                effective = _effective_command_line(hook)
                if effective:
                    all_commands.append(effective)
        joined = " ".join(all_commands)
        self.assertIn(
            "codebase-map-poll.sh",
            joined,
            "codebase-map-poll.sh not registered in Stop hooks",
        )


if __name__ == "__main__":
    unittest.main()
