"""AC8 — env table includes a row for min_confidence frontmatter precedence.

The Environment-variables section of `protocols/autonomous-intelligence.md`
documents per-agent frontmatter precedence. Required substrings:
(i) the four-role enum verbatim, (ii) a worked precedence example with
'frontmatter wins', (iii) the `CLAUDE_DISABLE_INSTINCT_INJECTION` pointer,
(iv) a reference to `agent_min_confidence_loader.py`.
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC = REPO_ROOT / "protocols" / "autonomous-intelligence.md"

REVIEW_AGENTS = ["code-reviewer", "security-engineer", "patch-critic",
                 "spec-blind-validator"]


def _env_section() -> str:
    text = DOC.read_text()
    start = text.index("#### Environment variables")
    rest = text[start + len("#### Environment variables"):]
    nxt = re.search(r"\n#### ", rest)
    end = start + len("#### Environment variables") + (nxt.start() if nxt else len(rest))
    return text[start:end]


def _min_confidence_row(section: str) -> str:
    for line in section.splitlines():
        if "min_confidence" in line and line.lstrip().startswith("|"):
            return line
    raise AssertionError("No row mentioning `min_confidence` found in env-variables table")


class EnvTable(unittest.TestCase):
    def test_env_table_row_contains_all_three_required_substrings(self):
        row = _min_confidence_row(_env_section())
        for name in REVIEW_AGENTS:
            self.assertIn(name, row,
                          f"min_confidence row must list {name} verbatim")
        self.assertIn("frontmatter wins", row,
                      "min_confidence row must show a worked example "
                      "containing 'frontmatter wins'")
        self.assertIn("CLAUDE_DISABLE_INSTINCT_INJECTION", row,
                      "min_confidence row must point at "
                      "CLAUDE_DISABLE_INSTINCT_INJECTION")

    def test_env_table_row_cites_loader(self):
        row = _min_confidence_row(_env_section())
        self.assertIn("agent_min_confidence_loader", row,
                      "min_confidence row must reference "
                      "`agent_min_confidence_loader.py`")


if __name__ == "__main__":
    unittest.main()
