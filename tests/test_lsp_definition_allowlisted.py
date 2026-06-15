"""AC4: All 3 engineer agents frontmatters contain both definition tools.

Proves pre-agent-allowlist.sh subset-check will admit definition calls.
"""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_AGENTS_DIR = REPO_ROOT / "agents"

_DEFINITION_TOOLS = {"mcp_lsp_definition_ts", "mcp_lsp_definition_py"}
_ENGINEER_AGENTS = ["software-engineer", "fix-engineer", "frontend-engineer"]


def _load_tools(agent_name):
    from agent_tools_loader import load_agent_tools
    import os
    os.environ["CLAUDE_AGENTS_DIR"] = str(_AGENTS_DIR)
    return set(load_agent_tools(agent_name))


class TestDefinitionToolsInEngineerFrontmatter(unittest.TestCase):
    def test_software_engineer_has_definition_tools(self):
        tools = _load_tools("software-engineer")
        missing = _DEFINITION_TOOLS - tools
        self.assertFalse(missing, f"software-engineer missing: {missing}")

    def test_fix_engineer_has_definition_tools(self):
        tools = _load_tools("fix-engineer")
        missing = _DEFINITION_TOOLS - tools
        self.assertFalse(missing, f"fix-engineer missing: {missing}")

    def test_frontend_engineer_has_definition_tools(self):
        tools = _load_tools("frontend-engineer")
        missing = _DEFINITION_TOOLS - tools
        self.assertFalse(missing, f"frontend-engineer missing: {missing}")
