"""Slice B graph + PageRank acceptance tests.

ACs covered: AC8 (def→ref edges weighted), AC10 (mentioned-files
reweight). AC9 / AC12 byte-equal determinism live in
`tests/test_codebase_map_determinism.py`.

Test names match `pipeline-state/auto-codebase-map/plan.md` § Slice B
Failing Test Stubs verbatim.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from codebase_map import graph as graph_mod  # noqa: E402
from codebase_map.tags_types import Tag  # noqa: E402


def _tag(file: str, kind: str, name: str, line: int = 1) -> Tag:
    return Tag(file=file, mtime=0.0, kind=kind, name=name,
               line=line, col=0, lang="python")


class AC8DefRefEdgesWeighted(unittest.TestCase):
    """Edges run def → ref with weight = ref count."""

    def test_ac8_def_ref_edges_weighted(self) -> None:
        # foo.py defines `helper`; bar.py and baz.py both reference it.
        # baz.py references it twice. Edges should be:
        #   bar.py → foo.py weight=1   (bar refs helper-defined-in-foo)
        #   baz.py → foo.py weight=2
        tags = [
            _tag("foo.py", "def", "helper", line=1),
            _tag("bar.py", "ref", "helper", line=10),
            _tag("baz.py", "ref", "helper", line=20),
            _tag("baz.py", "ref", "helper", line=21),
        ]
        g = graph_mod.build_graph(tags)
        self.assertIn("bar.py", g.nodes)
        self.assertIn("foo.py", g.nodes)
        self.assertIn("baz.py", g.nodes)
        # def → ref direction: ref-site files point to def-site files
        # (consumers point to providers — so personalized PageRank's
        # personalisation flowing from "mentioned consumer" reaches the
        # provider via outgoing edges).
        self.assertEqual(g["bar.py"]["foo.py"]["weight"], 1)
        self.assertEqual(g["baz.py"]["foo.py"]["weight"], 2)


class AC10MentionedFilesReweight(unittest.TestCase):
    """`personalized_pagerank(graph, mentioned=[...])` differs from unweighted."""

    def test_ac10_mentioned_files_reweight(self) -> None:
        # Build a graph where mentioning "foo.py" should bias scores
        # towards it (and its successors).
        tags = [
            _tag("foo.py", "def", "helper"),
            _tag("bar.py", "ref", "helper"),
            _tag("baz.py", "ref", "helper"),
            _tag("bar.py", "def", "other"),
            _tag("foo.py", "ref", "other"),
        ]
        g = graph_mod.build_graph(tags)

        unweighted = graph_mod.personalized_pagerank(g, mentioned=None)
        weighted = graph_mod.personalized_pagerank(
            g, mentioned=["foo.py"])

        # The two distributions must differ.
        # (At least one node's score must change — typically every node
        # shifts when the personalisation vector concentrates on one
        # node.)
        differs = any(
            abs(unweighted[n] - weighted[n]) > 1e-9 for n in g.nodes
        )
        self.assertTrue(
            differs,
            "personalized_pagerank with mentioned=[foo.py] produced the "
            f"same distribution as the unweighted call: {unweighted!r}",
        )


if __name__ == "__main__":
    unittest.main()
