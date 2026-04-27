"""YAML-aware loader for the `tools:` field of an agent frontmatter file.

Returns a list of strings when `tools:` is a YAML list, None otherwise.
Refuses to dereference traversal paths via `agent_path_validator`.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_tools_loader import load_agent_tools


class LoaderParsesYamlListTools(unittest.TestCase):
    def test_returns_list_for_yaml_list_tools_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent_file = Path(tmp) / "test-role.md"
            agent_file.write_text(
                "---\nname: test-role\ntools:\n  - Read\n  - Grep\n---\nbody")
            with patch.dict("os.environ", {"CLAUDE_AGENTS_DIR": tmp}):
                result = load_agent_tools("test-role")
            self.assertEqual(result, ["Read", "Grep"])


class LoaderReturnsNoneForNonListTools(unittest.TestCase):
    def _load(self, frontmatter_body):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "test-role.md").write_text(
                f"---\n{frontmatter_body}---\nbody")
            with patch.dict("os.environ", {"CLAUDE_AGENTS_DIR": tmp}):
                return load_agent_tools("test-role")

    def test_returns_none_for_inline_string_tools_field(self):
        self.assertIsNone(self._load("tools: Read, Grep\n"))

    def test_returns_none_for_empty_tools_field(self):
        self.assertIsNone(self._load("tools:\n"))

    def test_returns_none_when_tools_field_absent(self):
        self.assertIsNone(self._load("name: test-role\n"))


class LoaderRejectsTraversalSubagentType(unittest.TestCase):
    def test_traversal_subagent_type_returns_none(self):
        evil_dir = Path("/tmp/sec-poc-test-allowlist-loader")
        evil_dir.mkdir(parents=True, exist_ok=True)
        (evil_dir / "evil.md").write_text(
            "---\ntools:\n  - ATTACKER\n---\n")
        try:
            result = load_agent_tools(
                "../../../../tmp/sec-poc-test-allowlist-loader/evil")
            self.assertIsNone(result)
        finally:
            (evil_dir / "evil.md").unlink()
            evil_dir.rmdir()
