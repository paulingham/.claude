"""Tier 0 contract assertions for codebase_map.build / .render public surface.

Pinned by `pipeline-state/auto-codebase-map/plan.md` § Slice B Tier 0.

These tests fix the public-surface shape that downstream slices (C cli,
F integration) will re-import and re-assert against. Drift here is drift
everywhere — this is the canonical source of truth for Slice B ports.

Pinned facts:
- ``build`` signature: ``build(repo_root: Path, cache_dir: Path,
  mentioned: list[str] | None = None, budget: int = 1024,
  max_files: int | None = None) -> str``. Both positional and keyword
  invocation forms are supported.
- ``render`` token-budget invariant: ``count_tokens(output) <= budget``.
- ``personalized_pagerank`` returns a ``dict[str, float]`` whose values
  sum to 1.0 within numerical tolerance (probabilistic-distribution
  invariant).
"""
from __future__ import annotations

import inspect
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest
pytest.importorskip("networkx", reason="optional [codebase-map] dependency not installed")

from codebase_map import build as build_mod  # noqa: E402
from codebase_map import graph as graph_mod  # noqa: E402
from codebase_map import render as render_mod  # noqa: E402


class BuildSignaturePinned(unittest.TestCase):
    def test_build_signature_pinned(self) -> None:
        sig = inspect.signature(build_mod.build)
        params = list(sig.parameters.items())
        names = [n for n, _ in params]
        self.assertEqual(
            names,
            ["repo_root", "cache_dir", "mentioned", "budget", "max_files"],
        )
        defaults = {n: p.default for n, p in params}
        self.assertIs(defaults["mentioned"], None)
        self.assertEqual(defaults["budget"], 1024)
        self.assertIs(defaults["max_files"], None)

    def test_build_supports_keyword_invocation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            cache = Path(tmp) / "cache.sqlite"
            # keyword-only call shape
            out = build_mod.build(
                repo_root=repo,
                cache_dir=cache,
                mentioned=None,
                budget=1024,
                max_files=None,
            )
            self.assertIsInstance(out, str)

    def test_build_supports_positional_invocation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            cache = Path(tmp) / "cache.sqlite"
            # positional-args call shape
            out = build_mod.build(repo, cache)
            self.assertIsInstance(out, str)


class RenderTokenBudgetInvariant(unittest.TestCase):
    def test_render_output_tokens_within_budget(self) -> None:
        # Construct a graph with 5 fake symbols at varying ranks
        graph = graph_mod.build_graph([])
        scores = {f"sym_{i}": (5 - i) * 0.1 for i in range(5)}
        for sym in scores:
            graph.add_node(sym)
        budget = 64
        out = render_mod.render(graph, scores, budget=budget)
        self.assertLessEqual(render_mod.count_tokens(out), budget)


class PageRankProbabilityDistribution(unittest.TestCase):
    def test_pagerank_scores_sum_to_one(self) -> None:
        import networkx as nx
        g = nx.DiGraph()
        g.add_edge("a", "b", weight=2)
        g.add_edge("b", "c", weight=1)
        g.add_edge("c", "a", weight=1)
        scores = graph_mod.personalized_pagerank(g, mentioned=None)
        self.assertAlmostEqual(sum(scores.values()), 1.0, places=6)
        for v in scores.values():
            self.assertIsInstance(v, float)


if __name__ == "__main__":
    unittest.main()
