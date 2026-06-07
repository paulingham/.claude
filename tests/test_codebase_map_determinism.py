"""Slice B determinism acceptance tests.

ACs covered:
- AC9 — `personalized_pagerank(graph, mentioned=None)` deterministic
  across two calls in the same process AND across a fresh subprocess.
- AC12 — `build(...)` is byte-equal idempotent across two calls (with
  AND without `max_files`).

The architect's plan flags PageRank determinism as the load-bearing risk
surface — any non-determinism in the graph build, in score-dict ordering,
or in the render layer surfaces here as a byte-diff.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
pytest.importorskip("networkx", reason="optional [codebase-map] dependency not installed")

from codebase_map import build as build_mod  # noqa: E402
from codebase_map import graph as graph_mod  # noqa: E402
from codebase_map.tags_types import Tag  # noqa: E402


def _tag(file: str, kind: str, name: str) -> Tag:
    return Tag(file=file, mtime=0.0, kind=kind, name=name,
               line=1, col=0, lang="python")


def _fixture_graph():
    tags = [
        _tag("alpha.py", "def", "alpha_fn"),
        _tag("beta.py", "ref", "alpha_fn"),
        _tag("gamma.py", "ref", "alpha_fn"),
        _tag("beta.py", "def", "beta_fn"),
        _tag("gamma.py", "ref", "beta_fn"),
        _tag("alpha.py", "ref", "beta_fn"),
    ]
    return graph_mod.build_graph(tags)


class AC9PagerankByteEqual(unittest.TestCase):
    """In-process determinism: two calls produce byte-equal output.

    Notably we serialise WITHOUT ``sort_keys`` because the function's
    own contract is to return a stable-ordered dict — relying on
    ``sort_keys`` in the test would mask a regression where the dict
    iteration order drifted (the rendered output would still vary in
    other code paths that consume the dict directly).
    """

    def test_ac9_pagerank_byte_equal(self) -> None:
        g = _fixture_graph()
        s1 = graph_mod.personalized_pagerank(g, mentioned=None)
        s2 = graph_mod.personalized_pagerank(g, mentioned=None)
        # Identity on the dict shape AND on the iteration order.
        self.assertEqual(
            json.dumps(s1),
            json.dumps(s2),
        )
        # Stable iteration order: keys MUST come out alphabetically
        # sorted — this is the function's contract, and asserting it
        # directly catches mutations that remove the final sort even
        # when the small fixture's set order happens to be stable.
        self.assertEqual(list(s1.keys()), sorted(s1.keys()))


class AC9PagerankByteEqualSubprocess(unittest.TestCase):
    """Cross-process determinism: identical output in a fresh interpreter.

    A separate subprocess avoids any in-process state leakage (random
    seeds, hash-randomisation across re-imports). The subprocess script
    constructs the same graph, runs PageRank, and emits json-sorted
    scores to stdout — we assert that output is byte-equal to a
    reference run captured in this process.
    """

    def test_ac9_pagerank_byte_equal_subprocess(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        # Reference: in-process call. Serialise without ``sort_keys`` —
        # we want the test to be sensitive to iteration-order drift.
        g = _fixture_graph()
        scores = graph_mod.personalized_pagerank(g, mentioned=None)
        reference = json.dumps(scores)

        script = textwrap.dedent(
            """
            import json, sys
            from collections import namedtuple
            sys.path.insert(0, sys.argv[1])
            from codebase_map import graph as g
            Tag = namedtuple("Tag", "file mtime kind name line col lang")
            def t(f, k, n):
                return Tag(f, 0.0, k, n, 1, 0, "python")
            tags = [
                t("alpha.py", "def", "alpha_fn"),
                t("beta.py", "ref", "alpha_fn"),
                t("gamma.py", "ref", "alpha_fn"),
                t("beta.py", "def", "beta_fn"),
                t("gamma.py", "ref", "beta_fn"),
                t("alpha.py", "ref", "beta_fn"),
            ]
            graph = g.build_graph(tags)
            print(json.dumps(g.personalized_pagerank(graph, mentioned=None)))
            """
        ).strip()

        # Subprocess uses an explicit hash seed differing from the
        # reference run's default — if the function's iteration order
        # were hash-dependent (e.g. the inner ``sorted`` removed),
        # outputs would diverge. The PYTHONHASHSEED shifts catch that.
        result = subprocess.run(
            [sys.executable, "-c", script, str(repo_root)],
            capture_output=True,
            text=True,
            check=True,
            env={"PYTHONHASHSEED": "12345"},
        )
        self.assertEqual(result.stdout.strip(), reference)


class AC12BuildIdempotentByteEqual(unittest.TestCase):
    """`build(...)` returns byte-equal markdown across two calls.

    Tested with AND without `max_files` to cover both paths.
    """

    def _make_repo(self, tmp: Path) -> Path:
        repo = tmp / "repo"
        repo.mkdir()
        (repo / "module_a.py").write_text(
            "def alpha():\n    return beta()\n\ndef beta():\n    return 1\n"
        )
        (repo / "module_b.py").write_text(
            "def gamma():\n    return 2\n\ndef delta():\n    return gamma()\n"
        )
        return repo

    def test_ac12_build_idempotent_byte_equal_no_max_files(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            repo = self._make_repo(tmp)
            cache_a = tmp / "cache_a.sqlite"
            cache_b = tmp / "cache_b.sqlite"

            m1 = build_mod.build(repo_root=repo, cache_dir=cache_a)
            m2 = build_mod.build(repo_root=repo, cache_dir=cache_b)
            self.assertEqual(m1, m2)

    def test_ac12_build_idempotent_byte_equal_with_max_files(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            repo = self._make_repo(tmp)
            cache_a = tmp / "cache_a.sqlite"
            cache_b = tmp / "cache_b.sqlite"

            m1 = build_mod.build(
                repo_root=repo, cache_dir=cache_a, max_files=50)
            m2 = build_mod.build(
                repo_root=repo, cache_dir=cache_b, max_files=50)
            self.assertEqual(m1, m2)


if __name__ == "__main__":
    unittest.main()
