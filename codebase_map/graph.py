"""Reference graph + personalized PageRank.

Pinned by `pipeline-state/auto-codebase-map/plan.md` § Slice B (AC8-AC10).

Graph shape (AC8):
    - Nodes are repo-relative file paths (str).
    - Edges run **ref-site → def-site** (consumer → provider) — so
      personalisation flowing FROM a "mentioned consumer" reaches the
      provider via outgoing edges. Edge weight = number of refs from
      the source file to symbols defined in the target file.

PageRank determinism (AC9 + AC12):
    - NetworkX's PageRank is iterative and depends on dict-iteration
      order of the input graph plus a deterministic teleport vector.
      Python 3.7+ guarantees insertion-ordered dicts; PageRank
      iteration is then byte-deterministic for a fixed graph build,
      fixed personalisation vector, and fixed numeric tolerances.
    - We pass ``alpha=0.85`` and ``max_iter=100`` explicitly so a
      future NetworkX default change cannot change scores. ``tol`` is
      pinned at ``1e-6``. The implementation does NOT use random
      seeds — `networkx.pagerank` is fully deterministic given fixed
      inputs and fixed iteration parameters.

Mentioned-files weighting (AC10):
    - When ``mentioned`` is non-empty, the personalisation vector
      concentrates uniform mass on the mentioned files (any not in
      the graph are silently dropped). When ``mentioned`` is None or
      empty after filtering, ``personalisation`` is left as None so
      NetworkX uses the default (uniform) teleport — which also keeps
      the unweighted/weighted code path the same shape, only the
      vector differs.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence

import networkx as nx
from networkx.algorithms.link_analysis.pagerank_alg import _pagerank_python

from codebase_map.tags_types import Tag

# Iteration constants — pinned for determinism across NetworkX upgrades.
_ALPHA = 0.85
_MAX_ITER = 100
_TOL = 1.0e-6


def build_graph(tags: Iterable[Tag]) -> nx.DiGraph:
    """Build a directed reference graph from def/ref tags.

    Edges run ref-site → def-site with ``weight`` = number of
    references from the ref-file to symbols defined in the def-file.
    Files appearing only as defs (zero refs) are still added as
    isolated nodes so PageRank reaches them.
    """
    tag_list = list(tags)
    defs_by_name = _index_defs_by_name(tag_list)
    graph: nx.DiGraph = nx.DiGraph()
    _add_file_nodes(graph, tag_list)
    _add_edges_from_refs(graph, tag_list, defs_by_name)
    return graph


def personalized_pagerank(
    graph: nx.DiGraph,
    mentioned: Sequence[str] | None = None,
) -> dict[str, float]:
    """Run personalised PageRank with deterministic iteration parameters.

    When ``mentioned`` lists at least one node present in the graph,
    that node-set carries the entire personalisation mass uniformly;
    otherwise the call falls back to NetworkX's default (uniform)
    teleport — preserving the AC9 determinism contract for both paths.
    """
    if graph.number_of_nodes() == 0:
        return {}
    personalisation = _personalisation_vector(graph, mentioned)
    # Pure-Python implementation chosen over the scipy/numpy default
    # for two reasons: (a) no numpy/scipy harness dependency, (b) the
    # pure-Python iterative path is byte-deterministic for fixed inputs
    # — the AC9 contract — without depending on BLAS / SIMD vagaries.
    scores = _pagerank_python(
        graph,
        alpha=_ALPHA,
        personalization=personalisation,
        max_iter=_MAX_ITER,
        tol=_TOL,
        weight="weight",
    )
    # NetworkX returns a dict iterating in graph-node insertion order.
    # ``_add_file_nodes`` already inserted nodes in alphabetical order,
    # so the resulting dict iterates alphabetically — the AC9 contract.
    # We coerce to ``float`` (NetworkX may return numpy floats with the
    # scipy backend; we use the python backend but the cast is cheap
    # insurance against future backend swaps).
    return {n: float(scores[n]) for n in scores}


def _index_defs_by_name(tags: list[Tag]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for t in tags:
        if t.kind == "def":
            out.setdefault(t.name, []).append(t.file)
    return out


def _add_file_nodes(graph: nx.DiGraph, tags: list[Tag]) -> None:
    for f in sorted({t.file for t in tags}):
        graph.add_node(f)


def _add_edges_from_refs(
    graph: nx.DiGraph,
    tags: list[Tag],
    defs_by_name: dict[str, list[str]],
) -> None:
    edge_weights: Counter[tuple[str, str]] = Counter()
    for t in tags:
        if t.kind != "ref":
            continue
        for def_file in defs_by_name.get(t.name, ()):
            if def_file == t.file:
                continue  # ignore self-references
            edge_weights[(t.file, def_file)] += 1
    for (src, dst), weight in sorted(edge_weights.items()):
        graph.add_edge(src, dst, weight=weight)


def _personalisation_vector(
    graph: nx.DiGraph,
    mentioned: Sequence[str] | None,
) -> dict[str, float] | None:
    if not mentioned:
        return None
    in_graph = [m for m in mentioned if m in graph]
    if not in_graph:
        return None
    weight = 1.0 / len(in_graph)
    return {n: (weight if n in in_graph else 0.0) for n in graph}
