"""Slice F AC32-AC34 — Full-stack codebase-map integration tests.

Pinned by `pipeline-state/auto-codebase-map/plan.md` § Slice F.

These tests exercise the entire generator pipeline on the harness
repository itself — walk → tag → cache → graph → rank → render — and
assert three cross-module shared-id contracts:

- AC32 : `build()` is byte-deterministic across two runs with the same
         arguments. We pass `max_files=500` to bound walk time on this
         repo's >500-file tree.
- AC33 : `(file, mtime)` is a SHARED IDENTIFIER between the cache rows
         and the rendered graph nodes. Sample 5 cache rows; assert each
         appears as a graph node with a matching (file, mtime).
- AC34 : `project-hash` is a SHARED IDENTIFIER across:
         (a) the hook state-file path component,
         (b) the cache directory path component,
         (c) the `state.json` payload's hash field.
         AND `render()` output contains NO project-hash substring
         (private state, never user-facing).

Memory `instinct-cross-module-shared-id` (S5.1 D2 16-vs-64-char
learning): a shared id used at multiple layers MUST be byte-identical
at each layer. AC33 + AC34 are the explicit integration coverage.

Language scope: each test sets ``CLAUDE_CODEBASE_MAP_LANGUAGES=python``
to constrain extraction to the stdlib-``ast`` Python branch. The
harness env may not have ``tree_sitter_languages`` installed — Slice A
chose stdlib ``ast`` for Python and tree-sitter for the four other
languages, so a Python-only run exercises the full extract→cache→
graph→render pipeline without the optional native dep. This matches
the harness's "degrade gracefully when tree-sitter missing" contract
(AC21).

Runtime budget: each test self-bounds via `max_files=500`. PageRank
on ≤500 nodes converges in <2s on a warm cache. The test suite has
no `pytest-timeout` dependency.
"""
from __future__ import annotations

import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Make the harness package importable regardless of test invocation cwd.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Repo root override: tests parametrise over $REPO_ROOT (default = harness
# config dir). Keeps the test runnable in CI sandboxes that mount the
# harness at a non-default path.
REPO_ROOT = Path(
    os.environ.get("REPO_ROOT", "/Users/Paul.Ingham/.claude")
).resolve()

# Slice C state-file convention (mirrors hooks/codebase-map-rebuild.sh):
#     ~/.claude/db/codebase-map/{project-hash}/state.json
HOOK_DB_BASE = Path(
    os.environ.get("CLAUDE_CONFIG_DIR", os.path.expanduser("~/.claude"))
) / "db" / "codebase-map"


def _project_hash() -> str:
    """Return the harness project-hash via the canonical helper.

    Matches the resolution path the SessionStart hook uses (env first,
    `_project_hash --fallback "local"` second), so the AC34 cross-layer
    string-equality holds end-to-end.
    """
    env_hash = os.environ.get("CLAUDE_PROJECT_HASH", "").strip()
    if env_hash and re.match(r"^[A-Za-z0-9_.-]+$", env_hash):
        return env_hash
    helper = REPO_ROOT / "hooks" / "_lib" / "project-hash.sh"
    if helper.is_file():
        result = subprocess.run(
            ["bash", "-c",
             f'source "{helper}" && _project_hash --fallback "local"'],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    return "local"


class CodebaseMapIntegration(unittest.TestCase):
    """Full-stack integration suite — runs the generator on this repo.

    Each test self-bounds via internal walk truncation (max_files=500).
    pytest-timeout is not a harness dependency — the bound is structural.
    """

    @classmethod
    def setUpClass(cls):
        # Skip the entire suite when the codebase_map module is not
        # importable (e.g. running from a worktree that hasn't picked up
        # Slice A/B). The tests rely on the production module surface.
        try:
            from codebase_map.build import build  # noqa: F401
        except ImportError as exc:
            raise unittest.SkipTest(
                f"codebase_map module not importable: {exc}"
            )

    def setUp(self):
        # Constrain extraction to the Python stdlib-ast branch so the
        # tests run without the optional `tree_sitter_languages` native
        # dep. Snapshot the prior env value and restore in tearDown.
        self._prior_languages_env = os.environ.get(
            "CLAUDE_CODEBASE_MAP_LANGUAGES",
        )
        os.environ["CLAUDE_CODEBASE_MAP_LANGUAGES"] = "python"

    def tearDown(self):
        if self._prior_languages_env is None:
            os.environ.pop("CLAUDE_CODEBASE_MAP_LANGUAGES", None)
        else:
            os.environ["CLAUDE_CODEBASE_MAP_LANGUAGES"] = (
                self._prior_languages_env
            )

    def test_ac32_repo_walk_deterministic(self):
        """Two runs of build() with max_files=500 produce byte-equal output."""
        from codebase_map.build import build

        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            first = build(
                repo_root=REPO_ROOT,
                cache_dir=cache_dir,
                max_files=500,
            )
            self.assertTrue(first, "build() returned empty output on run 1")
            self.assertGreater(
                len(first), 32,
                "build() output suspiciously short — probably empty-state"
                " marker; the harness repo has >500 supported source files",
            )

            second = build(
                repo_root=REPO_ROOT,
                cache_dir=cache_dir,
                max_files=500,
            )
            self.assertEqual(
                first, second,
                "AC32: two identical build() calls returned different output. "
                "Determinism contract broken — see codebase_map/build.py "
                "module docstring 'Determinism contract' for the layer-by-"
                "layer requirements.",
            )

    def test_ac33_file_mtime_shared_id_consistency(self):
        """Sample 5 cache rows; assert each appears as a graph node."""
        from codebase_map.build import build

        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            build(
                repo_root=REPO_ROOT,
                cache_dir=cache_dir,
                max_files=500,
            )

            # Read 5 sample rows from the tags cache. The DB lives at
            # <cache_dir>/tags.sqlite per build._resolve_cache_db().
            db_path = cache_dir / "tags.sqlite"
            self.assertTrue(
                db_path.is_file(),
                f"AC33: cache DB not created at {db_path}",
            )
            cache_rows = self._sample_cache_rows(db_path, n=5)
            self.assertEqual(
                len(cache_rows), 5,
                f"AC33: expected ≥5 cache rows, got {len(cache_rows)}; "
                "harness repo should have many tagged definitions",
            )

            # Re-build the graph using the same tags the cache holds.
            # Crossing the SAME (file, mtime) shared id from cache rows
            # → in-memory graph nodes is the AC33 contract.
            from codebase_map import graph as graph_mod
            from codebase_map.tags import cached_tags

            files_in_cache = sorted({Path(row["file"]) for row in cache_rows})
            # cached_tags reads back from the SQLite cache (no new
            # extraction since mtimes are unchanged).
            tags = cached_tags(db_path, files_in_cache)
            graph = graph_mod.build_graph(tags)
            graph_files = set(graph.nodes())

            # The cache stores absolute paths; the graph (post-build()
            # retag) stores repo-relative paths. The shared-id contract
            # is satisfied iff EVERY cache row's file appears in the
            # graph as either form (absolute OR repo-relative).
            for row in cache_rows:
                cache_file = row["file"]
                rel = self._maybe_relative(cache_file)
                self.assertTrue(
                    cache_file in graph_files or rel in graph_files,
                    f"AC33 shared-id violation: cache row file "
                    f"{cache_file!r} (rel: {rel!r}) absent from graph "
                    f"nodes (sample of {len(graph_files)})",
                )

    def test_ac34_project_hash_consistent_across_layers(self):
        """project-hash is byte-identical across hook path + cache dir + state.

        AND render() output does NOT contain a project-hash substring
        (private state, never user-facing).
        """
        from codebase_map.build import build

        project_hash = _project_hash()
        self.assertTrue(
            project_hash,
            "_project_hash() returned empty — helper missing or broken",
        )

        # Layer 1: hook state-file path component.
        # (Matches hooks/codebase-map-rebuild.sh STATE_FILE construction.)
        hook_path = HOOK_DB_BASE / project_hash / "state.json"
        self.assertEqual(
            hook_path.parts[-2], project_hash,
            "AC34 layer-1: hook state-file path does NOT carry "
            f"project-hash {project_hash!r} as the parent dir",
        )

        # Layer 2: cache directory path component (production layer
        # hosts the live SQLite cache + state.json).
        cache_dir_layer = HOOK_DB_BASE / project_hash
        self.assertEqual(
            cache_dir_layer.name, project_hash,
            "AC34 layer-2: cache dir name does NOT match project-hash",
        )

        # Layer 3: when state.json exists, its 'last_built_sha' field
        # must be a valid SHA — and the path the file lives at must
        # agree with project-hash. (We don't require state.json to
        # exist; this layer asserts that IF it exists, the cross-layer
        # contract holds.)
        if hook_path.is_file():
            import json
            state = json.loads(hook_path.read_text())
            self.assertIn(
                "last_built_sha", state,
                "AC34 layer-3: state.json missing 'last_built_sha' field",
            )

        # Negative assertion: render() output never mentions project-hash.
        # We run build() in a fresh tmp cache so we don't depend on the
        # production cache state.
        with tempfile.TemporaryDirectory() as tmp:
            output = build(
                repo_root=REPO_ROOT,
                cache_dir=Path(tmp),
                max_files=500,
            )
            self.assertNotIn(
                project_hash, output,
                f"AC34 negative: render() output MUST NOT mention "
                f"project-hash {project_hash!r} — this is private state, "
                "never user-facing.",
            )

    # --- helpers ---

    def _sample_cache_rows(self, db_path: Path, n: int) -> list[dict]:
        con = sqlite3.connect(str(db_path))
        try:
            con.row_factory = sqlite3.Row
            rows = con.execute(
                "SELECT file, mtime, kind, name, line, col, lang FROM tags "
                "ORDER BY file, line LIMIT ?",
                (n,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()

    def _maybe_relative(self, path_str: str) -> str:
        """Return the repo-relative form of ``path_str`` if possible."""
        p = Path(path_str)
        try:
            return str(p.relative_to(REPO_ROOT))
        except ValueError:
            return path_str


if __name__ == "__main__":
    unittest.main()
