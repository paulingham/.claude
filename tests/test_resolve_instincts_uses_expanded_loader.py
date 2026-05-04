"""C62-AC8: production caller resolve-instincts.py uses expanded loader.

Static read of the production hook entry script. Pins that the import + call
site uses load_expanded_instinct_categories (parent-chain-aware), not the
flat load_agent_instinct_categories. Without this pin, parent-chain logic
would pass unit tests while being dead in production.
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RESOLVER = REPO_ROOT / "hooks" / "_lib" / "resolve-instincts.py"


class ResolveInstinctsCallsExpandedLoader(unittest.TestCase):
    def test_production_caller_imports_load_expanded_instinct_categories(self):
        src = RESOLVER.read_text()
        self.assertIn(
            "from agent_parent_chain import load_expanded_instinct_categories",
            src,
            "resolve-instincts.py must import the expanded loader")
        self.assertIn("load_expanded_instinct_categories(sub)", src,
                      "production caller must invoke the expanded loader")
        # Flat call site removed from the production code path.
        self.assertNotIn(
            "load_agent_instinct_categories(sub)", src,
            "flat loader call must be removed from the spawn handler")


if __name__ == "__main__":
    unittest.main()
