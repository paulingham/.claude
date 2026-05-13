"""Slice B' AC4 — protocols/thinking-defaults.md refined for v2.1.140.

After the Build-time Redirect (2026-05-13) dropped AC1 (the hook flip), AC4
no longer claims the hook is enforced. The doc must instead reflect the
ACTUAL v2.1.140 state with precision:

- Advisory framing retained (hook stays log-only).
- The schema gap is named explicitly: per-spawn `tool_input.thinking.effort`
  field NOT exposed; `$CLAUDE_EFFORT` env var IS consumed via
  `thinking_resolver.py:40` (rule 2a, source token `"claude-effort-env"`).
- Promotion-to-enforced is gated on the per-spawn field landing in a future
  Claude Code release.

These tests assert literal-substring presence on the file content. Each
assertion is paired with a hand-mutation kill in Step 6.
"""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC = REPO_ROOT / "protocols" / "thinking-defaults.md"


class AdvisoryFramingRetained(unittest.TestCase):
    """AC4: advisory framing survives. The hook is NOT enforced at v2.1.140."""

    def test_protocols_thinking_defaults_still_advisory(self):
        body = DOC.read_text()
        # Any one of the three load-bearing advisory tokens must survive.
        # If all three vanish, the doc has been over-promoted to claim
        # enforcement — Iron Law on honest disclosure violated.
        advisory_tokens = ("advisory", "log-only", "log entry")
        present = [t for t in advisory_tokens if t in body]
        self.assertTrue(
            present,
            f"protocols/thinking-defaults.md must retain at least one of "
            f"{advisory_tokens!r} — found none. Doc has been incorrectly "
            f"promoted to enforced wording (AC1 was dropped from this pipeline).")


class SchemaGapClarified(unittest.TestCase):
    """AC4: the per-spawn schema gap is named explicitly at v2.1.140."""

    def test_protocols_thinking_defaults_names_perspawn_gap(self):
        body = DOC.read_text()
        # The per-spawn field path that v2.1.140 still does NOT expose.
        self.assertIn(
            "tool_input.thinking.effort", body,
            "protocols/thinking-defaults.md must name the per-spawn field "
            "path `tool_input.thinking.effort` so future readers know exactly "
            "which schema surface is missing.")
        # The "not yet exposed" hedge phrasing — anchors the advisory status.
        self.assertIn(
            "not yet exposed", body,
            "protocols/thinking-defaults.md must state the per-spawn field "
            "is `not yet exposed` at v2.1.140.")
        # The v2.1.140 version pin — anchors the doc to the harness state at
        # this moment in time so a future reader knows which release the
        # caveat targets.
        self.assertIn(
            "v2.1.140", body,
            "protocols/thinking-defaults.md must name v2.1.140 as the "
            "current harness release the caveat applies to.")


class ClaudeEffortConsumptionDocumented(unittest.TestCase):
    """AC4: $CLAUDE_EFFORT env var IS consumed — document the pathway."""

    def test_protocols_thinking_defaults_names_env_var_consumption(self):
        body = DOC.read_text()
        # The env var name is load-bearing — it's the operator-visible
        # surface for forcing effort today.
        self.assertIn(
            "CLAUDE_EFFORT", body,
            "protocols/thinking-defaults.md must name the `CLAUDE_EFFORT` "
            "env var as the path that IS consumed at v2.1.140.")
        # The resolver pathway — any of the three tokens is acceptable
        # since the doc may cite the file, the rule, or the source token.
        pathway_tokens = ("thinking_resolver.py", "rule 2a", "claude-effort-env")
        present = [t for t in pathway_tokens if t in body]
        self.assertTrue(
            present,
            f"protocols/thinking-defaults.md must cite the env-var consumption "
            f"pathway via at least one of {pathway_tokens!r} — found none. "
            f"Readers need to know where the resolution lands.")


if __name__ == "__main__":
    unittest.main()
