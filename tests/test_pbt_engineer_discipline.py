"""AC2.6 — `pbt-engineer` has the tool-result-fabrication-forbidden clause.

Asserts the canonical sentence and the GitHub issue reference are present
in the Operating Discipline section (verbatim from `qa-engineer:33`).
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENT_PATH = REPO_ROOT / "agents" / "pbt-engineer.md"


def test_agent_has_tool_fabrication_clause():
    body = AGENT_PATH.read_text()
    assert "Tool-result fabrication is forbidden" in body, (
        "pbt-engineer body must contain the canonical "
        "'Tool-result fabrication is forbidden' clause")
    assert "github.com/anthropics/claude-code/issues/10628" in body, (
        "pbt-engineer body must reference the canonical GitHub issue link")
