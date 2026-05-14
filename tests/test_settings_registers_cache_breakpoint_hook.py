"""Slice B AC-B7 — settings.json registers cache-breakpoint-injector.sh
at PreToolUse Agent index 6.

The new hook MUST sit at PreToolUse Agent index 6 — AFTER instinct-injector
(at index 5) and BEFORE verification-freshness-guard (which shifts from
index 6 to index 7).

Mirrors tests/test_settings_registers_freshness_hook.py shape.
"""
import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _hook_basenames():
    """Return PreToolUse Agent hook basenames in array order."""
    settings = json.loads((REPO_ROOT / "settings.json").read_text())
    agent_groups = [g for g in settings["hooks"]["PreToolUse"]
                    if g.get("matcher") == "Agent"]
    assert len(agent_groups) == 1, "expected exactly one Agent matcher group"
    names = []
    for h in agent_groups[0]["hooks"]:
        args = h.get("args", [])
        text = args[-1] if args else ""
        if "/hooks/" in text and ".sh" in text:
            tail = text.split("/hooks/")[-1].split(".sh")[0]
            names.append(tail)
    return names


class SettingsRegistersCacheBreakpointHook(unittest.TestCase):
    def test_cache_breakpoint_hook_registered_at_index_6_after_instinct_injector_before_freshness_guard(self):
        names = _hook_basenames()
        self.assertIn(
            "cache-breakpoint-injector", names,
            "cache-breakpoint-injector.sh not registered on PreToolUse Agent")
        self.assertEqual(
            names.index("cache-breakpoint-injector"), 6,
            "cache-breakpoint-injector MUST sit at PreToolUse Agent index 6 "
            "(after instinct-injector at 5, before verification-freshness-guard).")
        # Ordering invariants.
        self.assertEqual(
            names.index("instinct-injector"), 5,
            "instinct-injector must remain at index 5")
        self.assertEqual(
            names.index("verification-freshness-guard"), 7,
            "verification-freshness-guard must shift to index 7 after new hook insertion")

    def test_new_hook_does_not_displace_existing_hooks(self):
        names = _hook_basenames()
        for required in ("pipeline-state-guard", "agent-skill-reminder",
                         "pre-agent-thinking", "pre-agent-advisor",
                         "pre-agent-allowlist", "instinct-injector",
                         "verification-freshness-guard", "scratchpad-bytes",
                         "depth-guard", "runtime-guard"):
            self.assertIn(required, names,
                          f"existing hook {required} was removed")


if __name__ == "__main__":
    unittest.main()
