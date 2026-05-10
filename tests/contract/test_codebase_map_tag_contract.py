"""Tier 0 contract assertions for codebase_map.tags public surface.

Pinned by `pipeline-state/auto-codebase-map/plan.md` § Slice A Tier 0.

These tests fix the public-surface shape that downstream slices (B graph
build, C cli, F integration) will re-import and re-assert against. A
contract drift here is a contract drift everywhere — the test is the
canonical source of truth for the ports.

Pinned facts:
- `Tag` is a namedtuple with exactly the field set
  (file, mtime, kind, name, line, col, lang) in that order.
- `extract_tags(path)` accepts a single positional arg (path-like) and
  returns a list (NOT an iterator, NOT a generator) of `Tag` instances.
- `walk_repo(root, exclude_dirs=None)` accepts a root path and an
  optional exclude_dirs param; returns an iterable of `pathlib.Path`.
- `ensure_cache(db_path)` is idempotent: calling twice with the same
  path returns without raising and leaves a single schema_version row.
- `CodebaseMapDependencyMissing` exists and inherits from `Exception`.
"""
from __future__ import annotations

import inspect
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

# Importable from the worktree root. The codebase_map package sits at the
# repo top level alongside hooks/, skills/, tests/.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from codebase_map.tags import (  # noqa: E402
    CodebaseMapDependencyMissing,
    Tag,
    extract_tags,
    walk_repo,
)
from codebase_map._lib.schema import ensure_cache  # noqa: E402


class TagShapeContract(unittest.TestCase):
    """Tag namedtuple has exactly the documented field set, in order."""

    def test_tag_field_order_is_pinned(self):
        self.assertEqual(
            Tag._fields,
            ("file", "mtime", "kind", "name", "line", "col", "lang"),
        )

    def test_tag_is_a_namedtuple_subclass(self):
        # Namedtuples are tuples; instances are immutable and indexable.
        self.assertTrue(issubclass(Tag, tuple))


class ExtractTagsSignatureContract(unittest.TestCase):
    """extract_tags(path) signature is pinned to one positional arg."""

    def test_signature_has_exactly_one_positional(self):
        sig = inspect.signature(extract_tags)
        params = list(sig.parameters.values())
        self.assertEqual(len(params), 1)
        self.assertEqual(params[0].name, "path")


class WalkRepoSignatureContract(unittest.TestCase):
    """walk_repo(root, exclude_dirs=None) signature pinned."""

    def test_signature_has_root_and_optional_exclude_dirs(self):
        sig = inspect.signature(walk_repo)
        params = list(sig.parameters.values())
        self.assertEqual([p.name for p in params], ["root", "exclude_dirs"])
        self.assertIs(params[1].default, None)


class EnsureCacheIdempotencyContract(unittest.TestCase):
    """Two ensure_cache() calls produce one schema_version row, no raise."""

    def test_double_call_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "cache.sqlite"
            ensure_cache(db_path)
            ensure_cache(db_path)
            con = sqlite3.connect(str(db_path))
            try:
                row = con.execute(
                    "SELECT COUNT(*) FROM schema_version"
                ).fetchone()
                self.assertEqual(row[0], 1)
            finally:
                con.close()


class DependencyExceptionContract(unittest.TestCase):
    """CodebaseMapDependencyMissing exists and is a real Exception."""

    def test_exception_class_inheritance(self):
        self.assertTrue(issubclass(CodebaseMapDependencyMissing, Exception))


if __name__ == "__main__":
    unittest.main()
