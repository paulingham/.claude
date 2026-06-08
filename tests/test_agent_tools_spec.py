"""Snapshot tests pinning every agent's tools array to the F1 spec.

These tests lock in the per-agent tool allowlist agreed in wave2-F1. Any
future change to an agent's `tools:` field MUST update this spec. Drift
between agent frontmatter and intent is what these tests prevent.
"""
import unittest
from pathlib import Path

from agent_tools_loader import load_agent_tools

REPO_ROOT = Path(__file__).resolve().parents[1]


# Spec for the seven F1-touched roles. The other three roles
# (qa-engineer, security-engineer, session-memory-updater) are NOT
# pinned here — they were intentionally left untouched in F1.
_SPEC = {
    "architect": ["Read", "Grep", "Glob", "WebFetch", "WebSearch"],
    "code-reviewer": ["Read", "Grep", "Glob", "Bash"],
    "product-reviewer": ["Read", "Grep", "Glob", "WebFetch"],
    "software-engineer": ["Read", "Write", "Edit", "Bash", "Grep", "Glob",
                          "NotebookEdit", "ToolSearch",
                          "mcp_lsp_diagnostics_ts", "mcp_lsp_diagnostics_py"],
    "frontend-engineer": ["Read", "Write", "Edit", "Bash", "Grep", "Glob",
                          "NotebookEdit", "ToolSearch", "Computer",
                          "mcp_lsp_diagnostics_ts", "mcp_lsp_diagnostics_py",
                          "mcp_chrome_devtools_navigate_page",
                          "mcp_chrome_devtools_list_console_messages",
                          "mcp_chrome_devtools_list_network_requests"],
    "database-engineer": ["Read", "Write", "Edit", "Bash", "Grep", "Glob",
                          "NotebookEdit", "ToolSearch"],
    "infrastructure-engineer": ["Read", "Write", "Edit", "Bash", "Grep",
                                "Glob", "NotebookEdit", "ToolSearch"],
    "planning-agent": ["Read", "Grep", "Glob", "Edit"],
    "sandbox-verify-engineer": ["Read", "Grep", "Glob", "Bash"],
}


class EveryAgentToolsArrayMatchesSpec(unittest.TestCase):
    def test_each_role_matches_spec(self):
        import os
        os.environ["CLAUDE_AGENTS_DIR"] = str(REPO_ROOT / "agents")
        for role, expected in _SPEC.items():
            actual = load_agent_tools(role)
            self.assertEqual(actual, expected,
                             f"{role}: tools drift detected")
