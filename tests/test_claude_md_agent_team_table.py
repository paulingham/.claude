"""B6-AC9: CLAUDE.md Agent Team table reflects Sonnet executors for SE/FE.

After Wave 5 / B6, both software-engineer and frontend-engineer rows must
report Default Model = sonnet (case-insensitive). The table is the
externally-visible source of truth for what model spawns when.
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC = REPO_ROOT / "CLAUDE.md"


def _agent_team_rows():
    text = DOC.read_text()
    match = re.search(
        r"###\s+Agent Team\b(.+?)(?=\n###\s+|\n##\s+|\Z)",
        text, re.DOTALL)
    return match.group(1) if match else ""


def _default_model(role, table):
    pattern = rf"\|\s*{re.escape(role)}\s*\|.*?\|.*?\|\s*([a-zA-Z0-9_-]+)\s*\|"
    match = re.search(pattern, table)
    return match.group(1).lower() if match else None


class AgentTeamTableReflectsSonnetExecutors(unittest.TestCase):
    def test_software_and_frontend_engineer_default_model_is_sonnet(self):
        table = _agent_team_rows()
        self.assertTrue(table, "Agent Team section not found in CLAUDE.md")
        self.assertEqual(_default_model("software-engineer", table), "sonnet")
        self.assertEqual(_default_model("frontend-engineer", table), "sonnet")


if __name__ == "__main__":
    unittest.main()
