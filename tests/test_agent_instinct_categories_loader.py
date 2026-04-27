"""Unit tests for hooks/_lib/agent_instinct_categories_loader.py."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hooks" / "_lib"))

from agent_instinct_categories_loader import load_agent_instinct_categories


class LoaderReturnsListForYamlList(unittest.TestCase):
    def test_block_style_list_returned(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "test-role.md").write_text(
                "---\nname: test-role\ninstinct_categories:\n"
                "  - software-engineer\n  - frontend-engineer\n---\nbody")
            with patch.dict("os.environ", {"CLAUDE_AGENTS_DIR": tmp}):
                result = load_agent_instinct_categories("test-role")
            self.assertEqual(result, ["software-engineer", "frontend-engineer"])

    def test_flow_style_list_returned(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "test-role.md").write_text(
                "---\nname: test-role\n"
                "instinct_categories: [a, b, c]\n---\nbody")
            with patch.dict("os.environ", {"CLAUDE_AGENTS_DIR": tmp}):
                result = load_agent_instinct_categories("test-role")
            self.assertEqual(result, ["a", "b", "c"])


class LoaderReturnsNoneForNonList(unittest.TestCase):
    def _load(self, frontmatter_body):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "test-role.md").write_text(
                f"---\n{frontmatter_body}---\nbody")
            with patch.dict("os.environ", {"CLAUDE_AGENTS_DIR": tmp}):
                return load_agent_instinct_categories("test-role")

    def test_missing_key_returns_none(self):
        self.assertIsNone(self._load("name: test-role\n"))

    def test_inline_string_returns_none(self):
        self.assertIsNone(self._load("instinct_categories: a, b\n"))

    def test_empty_value_returns_none(self):
        self.assertIsNone(self._load("instinct_categories:\n"))


class LoaderRejectsTraversal(unittest.TestCase):
    def test_traversal_subagent_type_returns_none(self):
        evil_dir = Path("/tmp/sec-poc-instinct-cats-loader")
        evil_dir.mkdir(parents=True, exist_ok=True)
        (evil_dir / "evil.md").write_text(
            "---\ninstinct_categories:\n  - ATTACKER\n---\n")
        try:
            result = load_agent_instinct_categories(
                "../../../../tmp/sec-poc-instinct-cats-loader/evil")
            self.assertIsNone(result)
        finally:
            (evil_dir / "evil.md").unlink()
            evil_dir.rmdir()

    def test_subagent_type_with_slash_returns_none(self):
        self.assertIsNone(load_agent_instinct_categories("foo/bar"))


class LoaderHandlesMissingRole(unittest.TestCase):
    def test_nonexistent_role_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict("os.environ", {"CLAUDE_AGENTS_DIR": tmp}):
                self.assertIsNone(
                    load_agent_instinct_categories("does-not-exist"))


if __name__ == "__main__":
    unittest.main()
