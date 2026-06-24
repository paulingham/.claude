"""Lock the C7 contract: fix-cycle dispatch resolves to fix-engineer.

Asserts that `agents/fix-engineer.md` exists with the right frontmatter and
that the orchestrator's Review Phase Dispatch CHANGES_REQUESTED block routes
to `subagent_type: "fix-engineer"`, NOT `subagent_type: "software-engineer"`.
"""
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
FIX_ENGINEER_PATH = REPO_ROOT / "agents" / "fix-engineer.md"
SOFTWARE_ENGINEER_PATH = REPO_ROOT / "agents" / "software-engineer.md"
DISPATCH_PATH = REPO_ROOT / "orchestrator" / "parallel-dispatch-details.md"


def _parse_frontmatter(path: Path) -> dict:
    text = path.read_text()
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    return yaml.safe_load(text[4:end]) or {}


class FixEngineerRouting(unittest.TestCase):
    def test_fix_engineer_agent_file_exists(self):
        self.assertTrue(
            FIX_ENGINEER_PATH.exists(),
            f"{FIX_ENGINEER_PATH} must exist",
        )
        fm = _parse_frontmatter(FIX_ENGINEER_PATH)
        self.assertIsInstance(
            fm, dict,
            f"{FIX_ENGINEER_PATH.name}: frontmatter must parse as a YAML mapping",
        )
        self.assertTrue(fm, f"{FIX_ENGINEER_PATH.name}: frontmatter is empty")

    def test_fix_engineer_frontmatter_contract(self):
        fm = _parse_frontmatter(FIX_ENGINEER_PATH)
        self.assertEqual(fm.get("name"), "fix-engineer")
        # fix-engineer was demoted to Sonnet in the model-demotion pass
        # (commit e0fc32d); the orchestrator still escalates it to Opus
        # dynamically at higher budgets (see agents/fix-engineer.md § dispatch).
        self.assertEqual(fm.get("model"), "sonnet")
        from model_alias import resolve_model_alias
        self.assertEqual(fm.get("executor"), "mid",
                         "fix-engineer executor must be alias 'mid'")
        self.assertEqual(resolve_model_alias(fm.get("executor")), "claude-sonnet-4-6",
                         "alias 'mid' must resolve to claude-sonnet-4-6")
        self.assertEqual(fm.get("advisor"), "none",
                         "fix-engineer advisor must remain literal 'none'")
        cats = fm.get("instinct_categories")
        self.assertIsInstance(cats, list, "instinct_categories must be a list")
        self.assertIn("fix-engineer", cats)
        self.assertIn("software-engineer", cats)
        tools = fm.get("tools")
        self.assertIsInstance(tools, list, "tools must be a list")
        se_tools = _parse_frontmatter(SOFTWARE_ENGINEER_PATH).get("tools")
        self.assertEqual(
            tools, se_tools,
            "fix-engineer tools must match software-engineer tools exactly",
        )

    def test_in_cycle_fix_dispatch_routes_to_fix_engineer(self):
        lines = DISPATCH_PATH.read_text().splitlines()
        anchor_indices = [
            i for i, line in enumerate(lines) if 'name: "fix-engineer"' in line
        ]
        self.assertTrue(
            anchor_indices,
            f'No `name: "fix-engineer"` anchor found in {DISPATCH_PATH}',
        )
        for idx in anchor_indices:
            window = "\n".join(lines[max(0, idx - 20): idx + 21])
            self.assertIn(
                'subagent_type: "fix-engineer"', window,
                f"Agent block at line {idx + 1} must use "
                'subagent_type: "fix-engineer"',
            )
            self.assertNotIn(
                'subagent_type: "software-engineer"', window,
                f"Agent block at line {idx + 1} must NOT use "
                'subagent_type: "software-engineer"',
            )


if __name__ == "__main__":
    unittest.main()
