"""C62-AC1..AC5: parent-chain instinct inheritance.

Walks frontmatter `parent:` transitively. Cycle protection via visited-set.
Missing parent file → stderr warning + JSONL forensic record.
load_expanded_instinct_categories returns the union of own + ancestor flat
categories.
"""
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from agent_parent_chain import (
    resolve_parent_chain, load_expanded_instinct_categories,
)


def _write_agent(tmp, name, frontmatter):
    p = Path(tmp) / f"{name}.md"
    lines = ["---", f"name: {name}"]
    for k, v in frontmatter.items():
        if isinstance(v, list):
            lines.append(f"{k}:")
            lines.extend(f"  - {item}" for item in v)
        else:
            lines.append(f"{k}: {v}")
    lines.extend(["---", "", "# Body"])
    p.write_text("\n".join(lines) + "\n")


class _AgentsTmpdirCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._prev = os.environ.get("CLAUDE_AGENTS_DIR")
        os.environ["CLAUDE_AGENTS_DIR"] = self._tmp

    def tearDown(self):
        if self._prev is None:
            del os.environ["CLAUDE_AGENTS_DIR"]
        else:
            os.environ["CLAUDE_AGENTS_DIR"] = self._prev


class ResolveParentChainSimple(_AgentsTmpdirCase):
    def test_chain_terminates_at_root_when_no_parent(self):
        _write_agent(self._tmp, "software-engineer",
                     {"instinct_categories": ["software-engineer"]})
        self.assertEqual(resolve_parent_chain("software-engineer"), [])


class ResolveParentChainSingleHop(_AgentsTmpdirCase):
    def test_frontend_engineer_parent_is_software_engineer(self):
        _write_agent(self._tmp, "software-engineer",
                     {"instinct_categories": ["software-engineer"]})
        _write_agent(self._tmp, "frontend-engineer",
                     {"parent": "software-engineer",
                      "instinct_categories": ["frontend-engineer"]})
        self.assertEqual(resolve_parent_chain("frontend-engineer"),
                         ["software-engineer"])


class ResolveParentChainCycleProtection(_AgentsTmpdirCase):
    def test_cycle_does_not_loop_forever(self):
        _write_agent(self._tmp, "alpha", {"parent": "beta"})
        _write_agent(self._tmp, "beta", {"parent": "alpha"})
        with redirect_stderr(io.StringIO()):
            chain = resolve_parent_chain("alpha")
        self.assertIsInstance(chain, list)
        self.assertLess(len(chain), 10)


class ResolveParentChainMissingParentWarnsStderrAndJsonl(_AgentsTmpdirCase):
    def test_missing_parent_emits_stderr_and_jsonl(self):
        _write_agent(self._tmp, "child", {"parent": "ghost"})
        metrics_dir = Path(self._tmp) / "metrics" / "test-session"
        metrics_dir.mkdir(parents=True)
        os.environ["CLAUDE_METRICS_DIR"] = str(Path(self._tmp) / "metrics")
        os.environ["CLAUDE_SESSION_ID"] = "test-session"
        try:
            buf = io.StringIO()
            with redirect_stderr(buf):
                chain = resolve_parent_chain("child")
            self.assertEqual(chain, [])
            self.assertIn("parent-chain", buf.getvalue())
            self.assertIn("ghost", buf.getvalue())
            jsonl = metrics_dir / "parent-chain-warnings.jsonl"
            self.assertTrue(jsonl.exists())
            entry = json.loads(jsonl.read_text().strip().splitlines()[-1])
            self.assertEqual(entry["source"], "missing-parent")
            self.assertEqual(entry["agent"], "child")
            self.assertEqual(entry["missing"], "ghost")
        finally:
            del os.environ["CLAUDE_METRICS_DIR"]
            del os.environ["CLAUDE_SESSION_ID"]


class LoadExpandedInstinctCategories(_AgentsTmpdirCase):
    def test_frontend_engineer_includes_parent_categories(self):
        _write_agent(self._tmp, "software-engineer",
                     {"instinct_categories":
                      ["software-engineer", "database-engineer"]})
        _write_agent(self._tmp, "frontend-engineer",
                     {"parent": "software-engineer",
                      "instinct_categories": ["frontend-engineer"]})
        self.assertEqual(
            load_expanded_instinct_categories("frontend-engineer"),
            ["database-engineer", "frontend-engineer", "software-engineer"])


if __name__ == "__main__":
    unittest.main()
