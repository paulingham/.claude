"""Slice D AC-D5 — CLAUDE.md § Reversibility Escapes lists every PreToolUse
Agent reversibility env var the harness honours.

The four advisory hooks each have a CLAUDE_DISABLE_* escape; CLAUDE.md is
the canonical surface where operators discover them. Drift here is the
single highest-likelihood mode of "operator can't find escape" (Risk M2
in plan.md).
"""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class ReversibilityEscapesTableComplete(unittest.TestCase):
    def test_reversibility_escapes_table_complete(self):
        # CLAUDE.md keeps a pointer to the Reversibility Escapes surface;
        # the full env-var table now lives in protocols/agent-protocol.md
        # (CLAUDE.md was pruned to pointers — commit b606d59).
        claude_md = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn("Reversibility Escapes", claude_md)
        body = (REPO_ROOT / "protocols" / "agent-protocol.md").read_text(
            encoding="utf-8")
        for var in ("CLAUDE_DISABLE_TOOL_ALLOWLIST",
                    "CLAUDE_DISABLE_THINKING_GATE",
                    "CLAUDE_DISABLE_ADVISOR_GATE",
                    "CLAUDE_DISABLE_INSTINCT_INJECTION"):
            self.assertIn(var, body,
                          f"protocols/agent-protocol.md missing {var}")


if __name__ == "__main__":
    unittest.main()
