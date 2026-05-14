"""Slice 3: settings.json must register instinct-injector.sh at index 5 and
the full PreToolUse Agent hook order MUST match the canonical 10-entry snapshot.

The instinct-injector hook MUST sit at PreToolUse Agent index 5, AFTER
pre-agent-allowlist (index 4) and BEFORE verification-freshness-guard
(index 6), scratchpad-bytes (index 7), depth-guard (index 8), and
runtime-guard (index 9).

Decision hooks (thinking, advisor, allowlist, instinct, freshness-guard)
cluster contiguously before resource-cap guards (scratchpad-bytes,
depth-guard, runtime-guard). If the hook moves, this test fails.

The snapshot uses basename-from-args parsing because the harness wraps every
hook script in `bash -lc 'exec "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/X.sh"'`,
so `h["command"]` is always the literal "bash" — the actual hook identity
lives in `h["args"][-1]`.
"""
import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_ORDER = [
    "pipeline-state-guard",
    "agent-skill-reminder",
    "pre-agent-thinking",
    "pre-agent-advisor",
    "pre-agent-allowlist",
    "instinct-injector",
    "verification-freshness-guard",
    "scratchpad-bytes",
    "depth-guard",
    "runtime-guard",
]


def _hook_basenames():
    settings = json.loads((REPO_ROOT / "settings.json").read_text())
    agent_groups = [g for g in settings["hooks"]["PreToolUse"]
                    if g.get("matcher") == "Agent"]
    assert len(agent_groups) == 1, "expected exactly one Agent matcher group"
    out = []
    for h in agent_groups[0]["hooks"]:
        args = h.get("args", [])
        text = args[-1] if args else ""
        if "/hooks/" in text and ".sh" in text:
            tail = text.split("/hooks/")[-1].split(".sh")[0]
            out.append(tail)
    return out


class SettingsRegistersInstinctInjectorAtIndex5(unittest.TestCase):
    def test_instinct_injector_registered_at_index_5(self):
        names = _hook_basenames()
        self.assertIn("instinct-injector", names,
                      "instinct-injector.sh not registered on PreToolUse Agent")
        self.assertEqual(names.index("instinct-injector"), 5,
                         "instinct-injector.sh must be at index 5")

    def test_full_pretoolse_agent_hook_order_matches_snapshot(self):
        self.assertEqual(_hook_basenames(), EXPECTED_ORDER)

    def test_instinct_injector_sits_after_allowlist_before_freshness_guard(self):
        names = _hook_basenames()
        injector_idx = names.index("instinct-injector")
        allowlist_idx = names.index("pre-agent-allowlist")
        freshness_idx = names.index("verification-freshness-guard")
        self.assertGreater(injector_idx, allowlist_idx)
        self.assertLess(injector_idx, freshness_idx)
