"""Drift test: every agent file and the Teammate Prompt Template must carry the
hallucinated-tool-result anti-fabrication clause.

Reference: https://github.com/anthropics/claude-code/issues/10628 — Claude Code
agents have been observed fabricating tool-call results when the harness fails
to deliver one back. The clause is the spawn-prompt-channel defense: every
agent reads its role file on every spawn, and the Teammate Prompt Template is
the single source the orchestrator copies into every team spawn.

The test uses a substring check on a load-bearing fragment rather than a
full-text match — full-text match would fail on incidental whitespace edits
and discourage the rest of the clause from being kept verbatim. The fragment
"Tool-result fabrication is forbidden" is the load-bearing imperative; if it
goes missing or gets paraphrased, the clause has lost its identity.
"""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = REPO_ROOT / "agents"
DISPATCH_PROTOCOL = REPO_ROOT / "rules" / "_detail" / "parallel-dispatch-protocol.md"

CLAUSE_FRAGMENT = "Tool-result fabrication is forbidden"
TEMPLATE_SECTION_HEADER = "## Teammate Prompt Template"
TEMPLATE_SECTION_END = "## What This Protocol Is NOT"


def _agent_files() -> list:
    return sorted(p for p in AGENTS_DIR.glob("*.md") if p.is_file())


def _read_template_section(path: Path) -> str:
    text = path.read_text()
    start = text.find(TEMPLATE_SECTION_HEADER)
    if start == -1:
        return ""
    end = text.find(TEMPLATE_SECTION_END, start)
    return text[start:end] if end != -1 else text[start:]


class HallucinationClausePresentInEveryAgent(unittest.TestCase):
    def test_clause_in_every_agent_file(self):
        agents = _agent_files()
        self.assertGreater(len(agents), 0, "no agent files found under agents/")
        for path in agents:
            body = path.read_text()
            self.assertIn(
                CLAUSE_FRAGMENT,
                body,
                f"{path.name}: missing hallucinated-tool-result clause "
                f"fragment {CLAUSE_FRAGMENT!r}",
            )


class HallucinationClausePresentInTeammatePromptTemplate(unittest.TestCase):
    def test_clause_in_template_section(self):
        self.assertTrue(
            DISPATCH_PROTOCOL.exists(),
            f"missing dispatch protocol file at {DISPATCH_PROTOCOL}",
        )
        section = _read_template_section(DISPATCH_PROTOCOL)
        self.assertNotEqual(
            section,
            "",
            "Teammate Prompt Template section header not found in dispatch protocol",
        )
        self.assertIn(
            CLAUSE_FRAGMENT,
            section,
            f"Teammate Prompt Template missing fragment {CLAUSE_FRAGMENT!r}",
        )


if __name__ == "__main__":
    unittest.main()
