"""Per-agent tool allowlist resolver tests (incremental TDD).

Mirrors `tests/test_advisor_resolver.py` shape: pure resolver first, loader
+ path validator next, then stdin script + bash hook smoke. Path B (log-only)
because Agent input schema does not currently expose `allowed_tools`.
"""
import json
import os
import subprocess
import unittest
import uuid
from pathlib import Path

from tool_allowlist_resolver import resolve


class ResolverSkipsNonAgentTool(unittest.TestCase):
    def test_returns_skip_for_non_agent_tool(self):
        result = resolve(tool_name="Bash", tool_input={}, frontmatter_tools=None)
        self.assertEqual(result["action"], "skip")
        self.assertEqual(result["source"], "non-agent")


class ResolverSkipsInvalidSubagentType(unittest.TestCase):
    def test_returns_skip_when_subagent_type_invalid(self):
        result = resolve(tool_name="Agent",
                         tool_input={"subagent_type": "../../etc/passwd"},
                         frontmatter_tools=None)
        self.assertEqual(result["action"], "skip")
        self.assertEqual(result["source"], "invalid-subagent-type")


class ResolverAdvisoryWhenRoleUnknown(unittest.TestCase):
    def test_advisory_when_frontmatter_tools_is_none(self):
        # frontmatter_tools=None signals: agent file not found OR no tools field
        result = resolve(tool_name="Agent",
                         tool_input={"subagent_type": "ghost-role"},
                         frontmatter_tools=None)
        self.assertEqual(result["action"], "advisory")
        self.assertEqual(result["source"], "no-tools-declared")


class ResolverAdvisoryWhenAllowedToolsAbsent(unittest.TestCase):
    """Path B today — Agent input schema does not expose `allowed_tools`.
    The resolver records what it WOULD check rather than blocking."""

    def test_advisory_when_no_allowed_tools_in_tool_input(self):
        result = resolve(tool_name="Agent",
                         tool_input={"subagent_type": "software-engineer"},
                         frontmatter_tools=["Read", "Write", "Edit"])
        self.assertEqual(result["action"], "advisory")
        self.assertEqual(result["source"], "schema-absent")
