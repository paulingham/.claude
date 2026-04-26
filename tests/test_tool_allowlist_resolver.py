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
