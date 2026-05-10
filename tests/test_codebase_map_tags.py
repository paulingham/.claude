"""Slice A acceptance criteria for codebase_map.tags.

One test per AC, named exactly as listed in
`pipeline-state/auto-codebase-map/plan.md` § Slice A Failing Test Stubs.

ACs covered: AC1, AC2, AC2-bis, AC3, AC3-bis, AC4, AC5, AC6, AC7.

The test_ac1_extract_tags_python_sample test asserts the full Tag tuple
shape on a tiny in-memory Python source file. AC2 / AC2-bis filter at
walk-and-extract time. AC3 / AC3-bis pin SQLite cache invariants. AC4
/ AC5 / AC6 pin cache hit / mtime-bump / schema-drift behaviour.
AC7 pins the typed dependency-missing exception.
"""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from codebase_map import tags as tags_mod  # noqa: E402
from codebase_map._lib.schema import (  # noqa: E402
    SCHEMA_VERSION,
    ensure_cache,
)
from codebase_map.tags import (  # noqa: E402
    CodebaseMapDependencyMissing,
    Tag,
    cached_tags,
    extract_tags,
    walk_repo,
)


PY_SAMPLE = '''\
def hello(name):
    print(name)


hello("world")
'''


def _write_python_sample(directory: Path, filename: str = "sample.py") -> Path:
    path = directory / filename
    path.write_text(PY_SAMPLE, encoding="utf-8")
    return path


def _python_kinds(path: Path) -> set[str]:
    return {t.kind for t in extract_tags(path)}


class AC1ExtractTagsPythonSample(unittest.TestCase):
    """AC1: extract_tags returns Tag list with both def and ref kinds."""

    def test_ac1_extract_tags_python_sample(self):
        with tempfile.TemporaryDirectory() as tmp:
            sample = _write_python_sample(Path(tmp))
            result = extract_tags(sample)
            self.assertIsInstance(result, list)
            self.assertGreater(len(result), 0)
            for t in result:
                self.assertIsInstance(t, Tag)
                self.assertIn(t.kind, {"def", "ref"})
                self.assertEqual(t.lang, "python")
                self.assertEqual(t.file, str(sample))
                self.assertGreaterEqual(t.line, 1)
                self.assertGreaterEqual(t.col, 0)
            kinds = {t.kind for t in result}
            self.assertIn("def", kinds)
            self.assertIn("ref", kinds)
            names = {t.name for t in result}
            self.assertIn("hello", names)
            # Pin lineno extraction: the `hello` def is on line 1,
            # the `hello("world")` ref is on line 5. Guards against
            # mutation that defaults all lines to 1.
            ref_lines = {
                t.line for t in result
                if t.kind == "ref" and t.name == "hello"
            }
            self.assertIn(5, ref_lines)


class AC2LanguageAllowlistFilters(unittest.TestCase):
    """AC2: extract_tags returns [] for files outside the allowlist."""

    def test_ac2_language_allowlist_filters(self):
        with tempfile.TemporaryDirectory() as tmp:
            ts_path = Path(tmp) / "sample.ts"
            ts_path.write_text("function hi(){ console.log(1); }\n",
                               encoding="utf-8")
            with mock.patch.dict(
                os.environ,
                {"CLAUDE_CODEBASE_MAP_LANGUAGES": "python"},
            ):
                self.assertEqual(extract_tags(ts_path), [])


class AC2bisWalkRepoExcludesWorktreeSiblings(unittest.TestCase):
    """AC2-bis: defaults exclude six well-known dirs; env adds, never replaces."""

    def _scaffold_repo(self, root: Path) -> None:
        # Real source files at the repo root.
        (root / "src.py").write_text("a = 1\n", encoding="utf-8")
        # Each excluded dir gets a single Python file inside it.
        for sub in (
            "agent-foo",
            "node_modules",
            "dist",
            "build",
            ".git",
        ):
            (root / sub).mkdir(parents=True, exist_ok=True)
            (root / sub / "noise.py").write_text("x = 0\n", encoding="utf-8")
        # Nested .claude/worktrees/bar/ shape.
        (root / ".claude" / "worktrees" / "bar").mkdir(
            parents=True, exist_ok=True
        )
        (root / ".claude" / "worktrees" / "bar" / "noise.py").write_text(
            "y = 0\n", encoding="utf-8"
        )

    def test_ac2bis_walk_repo_excludes_worktree_siblings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._scaffold_repo(root)
            seen = {p.relative_to(root).as_posix()
                    for p in walk_repo(root)}
            self.assertIn("src.py", seen)
            for forbidden in ("agent-foo/noise.py",
                              "node_modules/noise.py",
                              "dist/noise.py",
                              "build/noise.py",
                              ".git/noise.py",
                              ".claude/worktrees/bar/noise.py"):
                self.assertNotIn(
                    forbidden, seen,
                    f"{forbidden} was not excluded by defaults",
                )

            # Env adds, never replaces. Add 'vendor' as a custom exclusion
            # and confirm BOTH the new pattern AND the defaults stay active.
            (root / "vendor").mkdir()
            (root / "vendor" / "v.py").write_text("v = 0\n", encoding="utf-8")
            with mock.patch.dict(
                os.environ,
                {"CLAUDE_CODEBASE_MAP_EXCLUDE_DIRS": "^vendor$"},
            ):
                seen2 = {p.relative_to(root).as_posix()
                         for p in walk_repo(root)}
            self.assertNotIn("vendor/v.py", seen2)
            # Defaults still active under env override.
            self.assertNotIn("agent-foo/noise.py", seen2)
            self.assertNotIn("node_modules/noise.py", seen2)


class AC3EnsureCacheIdempotent(unittest.TestCase):
    """AC3: ensure_cache creates WAL + schema_version, idempotent."""

    def test_ac3_ensure_cache_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "cache.sqlite"
            ensure_cache(db_path)
            ensure_cache(db_path)
            con = sqlite3.connect(str(db_path))
            try:
                journal = con.execute("PRAGMA journal_mode").fetchone()[0]
                self.assertEqual(journal.lower(), "wal")
                version_rows = con.execute(
                    "SELECT version FROM schema_version"
                ).fetchall()
                self.assertEqual(version_rows, [(SCHEMA_VERSION,)])
                tables = {
                    r[0] for r in con.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
                self.assertIn("tags", tables)
                self.assertIn("schema_version", tables)
            finally:
                con.close()


class AC3bisConcurrentEnsureCacheSafe(unittest.TestCase):
    """AC3-bis: 5 threads call ensure_cache; one schema_version row, no raise."""

    def test_ac3bis_concurrent_ensure_cache_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "cache.sqlite"
            errors: list[BaseException] = []
            barrier = threading.Barrier(5)

            def worker():
                try:
                    barrier.wait(timeout=5)
                    ensure_cache(db_path)
                except BaseException as exc:  # noqa: BLE001
                    errors.append(exc)

            threads = [threading.Thread(target=worker) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)
            self.assertEqual(errors, [], f"thread errors: {errors!r}")
            con = sqlite3.connect(str(db_path))
            try:
                count = con.execute(
                    "SELECT COUNT(*) FROM schema_version"
                ).fetchone()[0]
                self.assertEqual(count, 1)
            finally:
                con.close()


class AC4CacheHitNoTreeSitterCall(unittest.TestCase):
    """AC4: re-extracting an unchanged file uses cache (zero parser calls)."""

    def test_ac4_cache_hit_no_treesitter_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            sample = _write_python_sample(Path(tmp))
            db_path = Path(tmp) / "cache.sqlite"
            ensure_cache(db_path)
            # Cold miss: warm the cache.
            cached_tags(db_path, [sample])
            # Hot hit: parser must NOT run.
            with mock.patch.object(
                tags_mod, "extract_tags", wraps=extract_tags
            ) as spy:
                result = cached_tags(db_path, [sample])
            spy.assert_not_called()
            self.assertGreater(len(result), 0)


class AC5MtimeAdvanceInvalidates(unittest.TestCase):
    """AC5: mtime bump triggers re-extract; old rows replaced atomically."""

    def test_ac5_mtime_advance_invalidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            sample = _write_python_sample(Path(tmp))
            db_path = Path(tmp) / "cache.sqlite"
            ensure_cache(db_path)
            cached_tags(db_path, [sample])
            # Bump mtime in the future to force invalidation.
            old_mtime = sample.stat().st_mtime
            future = old_mtime + 10
            os.utime(sample, (future, future))
            sample.write_text(
                "def goodbye(name):\n    print(name)\n", encoding="utf-8"
            )
            os.utime(sample, (future, future))
            cached_tags(db_path, [sample])
            con = sqlite3.connect(str(db_path))
            try:
                rows = con.execute(
                    "SELECT mtime, name FROM tags WHERE file=?",
                    (str(sample),),
                ).fetchall()
            finally:
                con.close()
            self.assertGreater(len(rows), 0)
            mtimes = {r[0] for r in rows}
            names = {r[1] for r in rows}
            self.assertEqual(mtimes, {future})
            self.assertIn("goodbye", names)
            self.assertNotIn("hello", names)


class AC6SchemaVersionDriftDropsData(unittest.TestCase):
    """AC6: schema-version drift drops the tags data table; structure intact."""

    def test_ac6_schema_version_drift_drops_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            sample = _write_python_sample(Path(tmp))
            db_path = Path(tmp) / "cache.sqlite"
            ensure_cache(db_path)
            cached_tags(db_path, [sample])
            # Force the persisted version BACKWARDS (version 0 = drift).
            con = sqlite3.connect(str(db_path))
            try:
                con.execute("DELETE FROM schema_version")
                con.execute(
                    "INSERT INTO schema_version (version, applied_at) "
                    "VALUES (0, datetime('now'))"
                )
                con.commit()
            finally:
                con.close()
            ensure_cache(db_path)
            con = sqlite3.connect(str(db_path))
            try:
                tag_count = con.execute(
                    "SELECT COUNT(*) FROM tags"
                ).fetchone()[0]
                versions = [
                    r[0] for r in con.execute(
                        "SELECT version FROM schema_version"
                    ).fetchall()
                ]
                tables = {
                    r[0] for r in con.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
            finally:
                con.close()
            self.assertEqual(tag_count, 0)
            self.assertEqual(versions, [SCHEMA_VERSION])
            self.assertIn("tags", tables)


class AC7MissingDepRaisesTyped(unittest.TestCase):
    """AC7: missing tree_sitter_languages raises CodebaseMapDependencyMissing.

    The dep-missing case only fires for non-Python languages — Python
    is tagged via stdlib `ast`. A `.ts` fixture exercises the
    tree-sitter import path so the AC7 mock is reachable.
    """

    def test_ac7_missing_dep_raises_typed(self):
        with tempfile.TemporaryDirectory() as tmp:
            sample = Path(tmp) / "sample.ts"
            sample.write_text(
                "function hi(){ console.log(1); }\n", encoding="utf-8",
            )
            with mock.patch.object(
                tags_mod, "_get_parser",
                side_effect=ImportError("no module named "
                                        "tree_sitter_languages"),
            ):
                with self.assertRaises(CodebaseMapDependencyMissing) as ctx:
                    extract_tags(sample)
            self.assertIn("pip install", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
