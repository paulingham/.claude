"""Slice B AC-B4 — every CLAUDE_DISABLE_* gate variable MUST be named in
protocols/thinking-defaults.md, protocols/advisor-mode.md, and CLAUDE.md.

The grep is intentionally simple: substring match against literal env-var
names. The Reversibility Escapes contract is the harness's only operator-
discoverable list of run-time toggles for the four PreToolUse Agent hooks;
silent drift here is the single highest-likelihood failure mode (Risk M2
in plan.md).
"""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(path):
    return (REPO_ROOT / path).read_text(encoding="utf-8")


class EnvVarsPresentInProtocolsAndClaudeMd(unittest.TestCase):
    def test_thinking_gate_named_in_thinking_protocol(self):
        self.assertIn("CLAUDE_DISABLE_THINKING_GATE",
                      _read("protocols/thinking-defaults.md"))

    def test_advisor_gate_named_in_advisor_protocol(self):
        self.assertIn("CLAUDE_DISABLE_ADVISOR_GATE",
                      _read("protocols/advisor-mode.md"))

    def test_both_gates_named_in_claude_md(self):
        claude_md = _read("CLAUDE.md")
        self.assertIn("CLAUDE_DISABLE_THINKING_GATE", claude_md)
        self.assertIn("CLAUDE_DISABLE_ADVISOR_GATE", claude_md)

    def test_tool_allowlist_gate_named_in_claude_md(self):
        # Allowlist's existing disable gate must also be documented
        # alongside the new ones; the "Reversibility Escapes" surface is
        # the canonical place to discover all four.
        self.assertIn("CLAUDE_DISABLE_TOOL_ALLOWLIST", _read("CLAUDE.md"))


if __name__ == "__main__":
    unittest.main()
