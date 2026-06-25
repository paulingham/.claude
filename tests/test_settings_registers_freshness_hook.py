"""Slice 3 + Slice B AC-B7b + Windows dep gate: settings.json must register
verification-freshness-guard.sh at PreToolUse Agent index 8 (after
cache-breakpoint-injector at index 7, before scratchpad-bytes at index 9).

Originally placed at index 6 (Slice 3). When Slice B
(prompt-caching-breakpoints) inserts cache-breakpoint-injector.sh at index 6,
freshness-guard shifts to index 7. The Windows dependency gate (harness-
dependency-gate.sh, INV-7) is prepended at index 0, shifting freshness-guard
to index 8 and scratchpad-bytes to index 9.

Mirrors tests/test_settings_registers_allowlist_hook.py shape.
"""
import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _hook_basenames():
    """Return PreToolUse Agent hook basenames (e.g. 'verification-freshness-guard')."""
    settings = json.loads((REPO_ROOT / "settings.json").read_text())
    agent_groups = [g for g in settings["hooks"]["PreToolUse"]
                    if g.get("matcher") == "Agent"]
    assert len(agent_groups) == 1, "expected exactly one Agent matcher group"
    names = []
    for h in agent_groups[0]["hooks"]:
        # args looks like: ['-lc', 'exec "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/{basename}.sh"']
        args = h.get("args", [])
        text = args[-1] if args else ""
        # Parse the hook script basename from the exec command.
        if "/hooks/" in text and ".sh" in text:
            tail = text.split("/hooks/")[-1].split(".sh")[0]
            names.append(tail)
    return names


class SettingsRegistersFreshnessHook(unittest.TestCase):
    def test_freshness_guard_registered_at_index_8_after_new_cache_breakpoint_hook(self):
        names = _hook_basenames()
        self.assertIn("verification-freshness-guard", names,
                      "verification-freshness-guard.sh not registered")
        self.assertEqual(names.index("verification-freshness-guard"), 8,
                         "freshness-guard MUST sit at PreToolUse Agent index 8 "
                         "(harness-dependency-gate at 0, cache-breakpoint-injector at 7, "
                         "before scratchpad-bytes)")

    def test_freshness_guard_sits_after_instinct_injector_before_scratchpad_bytes(self):
        names = _hook_basenames()
        fg = names.index("verification-freshness-guard")
        ii = names.index("instinct-injector")
        sb = names.index("scratchpad-bytes")
        self.assertGreater(fg, ii, "freshness-guard must come AFTER instinct-injector")
        self.assertLess(fg, sb, "freshness-guard must come BEFORE scratchpad-bytes")


if __name__ == "__main__":
    unittest.main()
