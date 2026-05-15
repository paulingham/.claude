"""Slice C AC-C2 — Small-agent skip list documented in cache-audit SKILL.md.

The skill must enumerate the three small agents whose prelude is < 4096 tokens
(verified empirically — see plan.md C.2): `planning-agent`,
`sandbox-verify-engineer`, `vlm-critic`. These are documented as exempt from
prompt-cache breakpoint enforcement because their preludes fall below the
minimum cacheable threshold.
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "skills" / "cache-audit" / "SKILL.md"

_SMALL_AGENTS = ("planning-agent", "sandbox-verify-engineer", "vlm-critic")


class SmallAgentSkipListDocumented(unittest.TestCase):
    def test_small_agent_skip_list_documented(self):
        text = SKILL.read_text()
        self.assertRegex(
            text, r"##+\s+Small-agent skip list",
            "SKILL.md must contain a `## Small-agent skip list` subsection")
        section = re.search(
            r"##+\s+Small-agent skip list\s*\n(.+?)(?=\n##\s|\Z)",
            text, re.DOTALL)
        self.assertIsNotNone(section, "skip-list section body not found")
        body = section.group(1)
        for agent in _SMALL_AGENTS:
            self.assertIn(
                agent, body,
                f"`{agent}` must be enumerated in Small-agent skip list")


if __name__ == "__main__":
    unittest.main()
