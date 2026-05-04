"""C62-AC0a/b/c: shared file-I/O helpers for agent frontmatter.

Both the existing flat instinct_categories loader and the new parent-chain
loader depend on the same three helpers (agents_dir, read_frontmatter,
resolve_path). Extracted to keep both files within the 50-line shape ceiling.
"""
import os
import tempfile
import unittest
from pathlib import Path

from agent_frontmatter_io import agents_dir, read_frontmatter, resolve_path


class AgentsDirHonoursEnvOverride(unittest.TestCase):
    def test_claude_agents_dir_env_overrides_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["CLAUDE_AGENTS_DIR"] = tmp
            try:
                self.assertEqual(str(agents_dir()), tmp)
            finally:
                del os.environ["CLAUDE_AGENTS_DIR"]


class ReadFrontmatterParsesYaml(unittest.TestCase):
    def test_read_frontmatter_returns_dict_for_well_formed_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "agent.md"
            p.write_text("---\nname: alice\nrole: ops\n---\n\n# Body\n")
            fm = read_frontmatter(p)
            self.assertEqual(fm.get("name"), "alice")
            self.assertEqual(fm.get("role"), "ops")


class ResolvePathRefusesTraversal(unittest.TestCase):
    def test_resolve_path_returns_none_for_invalid_subagent_type(self):
        self.assertIsNone(resolve_path("../etc/passwd"))
        self.assertIsNone(resolve_path("foo/bar"))
        self.assertIsNone(resolve_path(""))


if __name__ == "__main__":
    unittest.main()
