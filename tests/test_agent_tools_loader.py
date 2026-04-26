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
