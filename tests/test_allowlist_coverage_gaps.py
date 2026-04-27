"""Gap-filling QA tests for the per-agent tool allowlist feature.

Locks coverage for AC1 (every agent declares tools), AC4 (docs section
exists, dynamic template uses YAML list), and YAML loader edge cases
(comments, blank lines). Concurrency coverage lives in
tests/test_allowlist_concurrency.py.
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_tools_loader import load_agent_tools

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_with(frontmatter):
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "edge.md").write_text(f"---\n{frontmatter}---\nbody")
        with patch.dict("os.environ", {"CLAUDE_AGENTS_DIR": tmp}):
            return load_agent_tools("edge")


class AllAgentsDeclareToolsList(unittest.TestCase):
    def test_every_top_level_agent_has_tools_list(self):
        os.environ["CLAUDE_AGENTS_DIR"] = str(REPO_ROOT / "agents")
        for agent_file in (REPO_ROOT / "agents").glob("*.md"):
            role = agent_file.stem
            tools = load_agent_tools(role)
            self.assertIsInstance(tools, list, f"{role}: tools missing")
            self.assertGreater(len(tools), 0, f"{role}: tools empty")


class AgentProtocolDocumentsScoping(unittest.TestCase):
    def test_protocol_section_exists_with_required_anchors(self):
        text = (REPO_ROOT / "rules" / "agent-protocol.md").read_text()
        self.assertIn("## Per-Agent Tool Scoping", text)
        for anchor in ("pre-agent-allowlist.sh", "agent_tools_loader",
                       "would_block", "CLAUDE_DISABLE_TOOL_ALLOWLIST",
                       "CLAUDE_HOOK_PROFILE=minimal"):
            self.assertIn(anchor, text, f"protocol missing: {anchor}")


class DynamicAgentTemplateUsesYamlList(unittest.TestCase):
    def test_template_tools_field_is_yaml_list(self):
        text = (REPO_ROOT / "orchestrator" / "agent-orchestration.md").read_text()
        self.assertIn("tools:\n  - Read", text)
        self.assertNotIn("tools: Read, Write, Edit, Bash, Grep, Glob", text)


class LoaderHandlesYamlEdgeCases(unittest.TestCase):
    def test_comments_in_tools_list_are_ignored(self):
        result = _load_with(
            "tools:\n  # primary tools\n  - Read\n  - Grep  # search\n")
        self.assertEqual(result, ["Read", "Grep"])

    def test_blank_lines_between_entries_are_tolerated(self):
        result = _load_with("tools:\n  - Read\n\n  - Grep\n")
        self.assertEqual(result, ["Read", "Grep"])


if __name__ == "__main__":
    unittest.main()
