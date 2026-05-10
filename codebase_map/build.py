"""Slice B orchestrator: walk → tag → graph → rank → render.

Pinned by `pipeline-state/auto-codebase-map/plan.md` § Slice B
(AC11-bis, AC12, AC13). The public entry point is ``build``.

Determinism contract
====================

``build(repo_root, cache_dir, ...)`` is **byte-equal idempotent** for
the same repo state. This requires every layer below it to be
deterministic:

- Walk: ``walk_repo`` yields filesystem-ordered paths; we re-sort to
  alphabetical by repo-relative path so the order is filesystem-
  independent. (AC11-bis truncation tiebreaker also depends on this.)
- Tag extraction: stdlib ``ast`` and (when present) ``tree_sitter``
  parsers are deterministic for the same source. The cache layer
  (`codebase_map._lib.cache`) keys on ``(file, mtime)`` and replays
  cached rows when mtime is unchanged.
- Graph build, PageRank: see `codebase_map.graph` module docstring
  for the determinism contract.
- Render: chars-per-token proxy + score-descending sort with
  alphabetical tiebreaker (see `codebase_map.render`).

Truncation contract (AC11-bis)
==============================

When ``max_files=N`` is supplied AND the walk yields more than N
supported files, the walk truncates to the alphabetically-first N
**repo-relative paths** and emits one stderr warning line:

    codebase-map: truncated walk at max_files={N} ({M} files seen)

The alphabetical sort (NOT mtime) is required for byte-determinism —
mtimes vary across filesystems and CI clones, which would break AC12.
"""
from __future__ import annotations

import sys
from collections.abc import Iterable
from pathlib import Path

from codebase_map import graph as graph_mod
from codebase_map import render as render_mod
from codebase_map._lib.schema import ensure_cache
from codebase_map.tags import cached_tags, walk_repo

_SUPPORTED_SUFFIXES = (".py", ".ts", ".tsx", ".js", ".jsx", ".rb", ".go")


def build(
    repo_root: Path,
    cache_dir: Path,
    mentioned: list[str] | None = None,
    budget: int = 1024,
    max_files: int | None = None,
) -> str:
    """Build the codebase-map markdown digest for ``repo_root``.

    Returns the rendered markdown. Caller is responsible for writing
    it to disk if persistence is desired.
    """
    repo_root = Path(repo_root)
    cache_db = _resolve_cache_db(Path(cache_dir))
    ensure_cache(cache_db)

    repo_files = _gather_supported_files(repo_root)
    repo_files = _apply_max_files_truncation(repo_files, max_files)
    if not repo_files:
        return render_mod.render(graph_mod.build_graph([]), {}, budget=budget)

    tags = cached_tags(cache_db, repo_files)
    rel_tags = _retag_relative_to_repo(tags, repo_root)
    graph = graph_mod.build_graph(rel_tags)
    scores = graph_mod.personalized_pagerank(graph, mentioned=mentioned)
    return render_mod.render(graph, scores, budget=budget)


def _resolve_cache_db(cache_dir: Path) -> Path:
    """Allow callers to pass either a SQLite file path or a directory.

    A path with a ``.sqlite`` (or ``.db``) suffix is treated as the DB
    file directly; anything else is treated as a directory and the DB
    lands at ``<dir>/tags.sqlite``.
    """
    if cache_dir.suffix in (".sqlite", ".db"):
        return cache_dir
    return cache_dir / "tags.sqlite"


def _gather_supported_files(repo_root: Path) -> list[Path]:
    """Walk repo, keep supported source files, sort by repo-relative path."""
    candidates = [
        f for f in walk_repo(repo_root)
        if f.suffix.lower() in _SUPPORTED_SUFFIXES
    ]
    return sorted(
        candidates,
        key=lambda p: str(_to_relative(p, repo_root)),
    )


def _apply_max_files_truncation(
    files: list[Path],
    max_files: int | None,
) -> list[Path]:
    """Truncate to alphabetically-first N files; emit one warning line."""
    if max_files is None or len(files) <= max_files:
        return files
    seen = len(files)
    print(
        f"codebase-map: truncated walk at max_files={max_files} "
        f"({seen} files seen)",
        file=sys.stderr,
    )
    return files[:max_files]


def _retag_relative_to_repo(
    tags: Iterable,
    repo_root: Path,
) -> list:
    """Rewrite Tag.file from absolute path to repo-relative path.

    Cross-module shared-id contract: graph nodes are repo-relative
    paths (Slice F AC33 + AC34 will assert this end-to-end).
    """
    out = []
    for t in tags:
        rel = str(_to_relative(Path(t.file), repo_root))
        out.append(t._replace(file=rel))
    return out


def _to_relative(path: Path, root: Path) -> Path:
    try:
        return path.relative_to(root)
    except ValueError:
        return path
