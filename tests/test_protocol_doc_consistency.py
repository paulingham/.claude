"""Slice D — protocol doc consistency after the 2026-05-14 hook flip.

The four PreToolUse Agent hooks no longer share a uniform status:
`pre-agent-allowlist.sh` is ENFORCING; the other three remain advisory.
Doc surfaces MUST distinguish "flipped" from "advisory pending schema"
or future debuggers will cite contradictory sources (Pre-Mortem failure
mode HIGH-3 in plan.md).

AC-D1: protocols/agent-tool-allowlists.md drops the "advisory at v2.1.140"
       characterisation for the allowlist gate; ENFORCING since 2026-05-14.
AC-D2/D3: thinking/advisor protocol pages preserve "advisory pending
       schema" wording AND cite probe-result.md.
AC-D4: protocols/autonomous-intelligence.md cross-references
       hooks/instinct-injector.sh and explains the mutation-semantic
       reason it stays advisory while allowlist flipped.
"""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(p):
    return (REPO_ROOT / p).read_text(encoding="utf-8")


class FlippedHooksDropAdvisoryLanguage(unittest.TestCase):
    """AC-D1: allowlist doc no longer says 'advisory at v2.1.140'."""

    def test_allowlist_protocol_says_enforcing(self):
        body = _read("protocols/agent-tool-allowlists.md")
        # Old advisory characterisation removed
        self.assertNotIn("Allowlist enforcement remains **advisory at v2.1.140**",
                         body)
        # New enforcement characterisation present
        self.assertIn("ENFORCING since 2026-05-14", body)
        self.assertIn("exit 2", body)


class AdvisoryHooksKeepHedgeAndCiteProbeResult(unittest.TestCase):
    """AC-D2/D3: thinking + advisor protocols preserve their advisory
    status AND cite probe-result.md as the schema-gap evidence."""

    def test_thinking_protocol_cites_probe_result(self):
        body = _read("protocols/thinking-defaults.md")
        self.assertIn("probe-result.md", body)
        # advisory hedge preserved
        self.assertIn("log-only", body)

    def test_advisor_protocol_keeps_advisory_hedge(self):
        body = _read("protocols/advisor-mode.md")
        self.assertIn("advisory at v2.1.140", body)


class InstinctAdvisoryRationaleStrengthened(unittest.TestCase):
    """AC-D4: autonomous-intelligence.md § Instinct Injection cross-
    references hooks/instinct-injector.sh AND names the mutation-semantic
    reason it stays advisory."""

    def test_instinct_advisory_rationale_strengthened(self):
        body = _read("protocols/autonomous-intelligence.md")
        self.assertIn("hooks/instinct-injector.sh", body)
        self.assertIn("mutation-semantic", body)


if __name__ == "__main__":
    unittest.main()
