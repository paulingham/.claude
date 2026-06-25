"""Slice 3: settings.json must register instinct-injector.sh at index 6 and
the full PreToolUse Agent hook order MUST match the canonical 16-entry snapshot.

The instinct-injector hook MUST sit at PreToolUse Agent index 6, AFTER
pre-agent-allowlist (index 5) and BEFORE verification-freshness-guard
(index 7), scratchpad-bytes (index 8), depth-guard (index 9),
runtime-guard (index 12), agentic-security-gate (index 13), and
intake-backstop (index 14).

Index 0 is now harness-dependency-gate (Windows prereq gate, prepended first
per INV-7: self-contained, fail-closed, must precede pipeline-state-guard
which calls python3 — see knowledge/windows-setup.md).

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
    # WHY: self-contained Windows prereq gate — prepended FIRST (INV-7) so it
    # runs before pipeline-state-guard.sh which calls python3 at line 36.
    "harness-dependency-gate",
    "pipeline-state-guard",
    "agent-skill-reminder",
    "pre-agent-thinking",
    "pre-agent-advisor",
    "pre-agent-allowlist",
    "instinct-injector",
    # Slice B (prompt-caching-breakpoints) inserts cache-breakpoint-injector
    # at index 7, shifting verification-freshness-guard to index 8.
    "cache-breakpoint-injector",
    "verification-freshness-guard",
    "scratchpad-bytes",
    # swe-pruner advisory context-pruning filter (#172) sits after the
    # scratchpad guard and before the resource-cap guards.
    "pre-agent-swe-pruner",
    "depth-guard",
    "runtime-guard",
    # WHY: enforcing agentic-spawn gate — between runtime-guard and intake-backstop, mirrors hooks.json
    "agentic-security-gate",
    "intake-backstop",
    # over-spawn advisory guard (GP-P2-04) — appended last, after intake-backstop.
    # Advisory exit-0 Agent hook at the tail of the decision/guard chain.
    "pre-agent-over-spawn-guard",
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
    def test_instinct_injector_registered_at_index_6(self):
        names = _hook_basenames()
        self.assertIn("instinct-injector", names,
                      "instinct-injector.sh not registered on PreToolUse Agent")
        self.assertEqual(names.index("instinct-injector"), 6,
                         "instinct-injector.sh must be at index 6 "
                         "(harness-dependency-gate prepended at index 0)")

    def test_full_pretoolse_agent_hook_order_matches_snapshot(self):
        self.assertEqual(_hook_basenames(), EXPECTED_ORDER)

    def test_instinct_injector_sits_after_allowlist_before_freshness_guard(self):
        names = _hook_basenames()
        injector_idx = names.index("instinct-injector")
        allowlist_idx = names.index("pre-agent-allowlist")
        freshness_idx = names.index("verification-freshness-guard")
        self.assertGreater(injector_idx, allowlist_idx)
        self.assertLess(injector_idx, freshness_idx)
