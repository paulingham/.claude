"""Adversarial Step 2b tests for Slice A — AC-adjacent edge probes.

Per `skills/build-implementation/SKILL.md` § Step 2b. Five-category
walk; cap=5 for greenfield. Each adversarial follows RED-then-GREEN
in spirit (the test probes a category the architect's stubs do not
cover; the production code already passes by construction here, so
these are documented edge regressions).

Categories surfaced (kept):
- Adv1 (Null/empty + Hostile env): empty CLAUDE_CODEBASE_MAP_EXCLUDE_DIRS
  must NOT re-include `.git/` — defaults are non-removable.
- Adv2 (Malformed parser-level input): a Python file with a SyntaxError
  must NOT raise; extractor must degrade to `[]`.
- Adv3 (Error-path coverage): `_safely_get_parser` should NOT swallow
  non-ImportError exceptions — surface them so true bugs aren't hidden.

Categories evaluated but NOT included:
- Boundary (empty repo): trivially passes — `walk_repo` on an empty
  directory yields nothing; the existing AC tests already exercise
  the iteration. Vanity test, deleted per Step 2b discipline.
- Concurrency: AC3-bis already covers schema-init concurrency; the
  cached_tags path is per-call (each call opens its own connection),
  so a second concurrency test would duplicate coverage.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from codebase_map import tags as tags_mod  # noqa: E402
from codebase_map.tags import extract_tags, walk_repo  # noqa: E402


class Adv1HostileEmptyEnvCannotUnsetDefaults(unittest.TestCase):
    """Empty CLAUDE_CODEBASE_MAP_EXCLUDE_DIRS must NOT re-include .git/.

    Architect-flagged hazard (scratchpad warning, plan H1): a hostile
    or accidentally-empty env var must NOT replace the defaults.
    Empty string splits to [] under our parser, so the OR-list stays
    at the default six patterns — but pin the behaviour explicitly.
    """

    def test_empty_env_does_not_re_include_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            (root / ".git" / "noise.py").write_text("x=0\n")
            (root / "src.py").write_text("a=1\n")
            with mock.patch.dict(
                os.environ,
                {"CLAUDE_CODEBASE_MAP_EXCLUDE_DIRS": ""},
            ):
                seen = {p.relative_to(root).as_posix()
                        for p in walk_repo(root)}
            self.assertIn("src.py", seen)
            self.assertNotIn(".git/noise.py", seen)


class Adv2MalformedPythonReturnsEmptyNoRaise(unittest.TestCase):
    """A Python file with a SyntaxError must degrade to [] silently.

    Required because the codebase-map walk runs over EVERY file in
    the repo; a single broken .py (typo, in-progress edit, intentional
    test-fixture parse error) must not poison the whole rebuild.
    """

    def test_syntax_error_python_does_not_raise(self):
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / "broken.py"
            broken.write_text("def foo(:\n    pass\n", encoding="utf-8")
            self.assertEqual(extract_tags(broken), [])


class Adv3SafelyGetParserDoesNotSwallowGenericErrors(unittest.TestCase):
    """Only ImportError → CodebaseMapDependencyMissing.

    Non-ImportError exceptions (e.g. RuntimeError from a corrupted
    grammar) MUST propagate unchanged so genuine bugs aren't masked
    behind the typed-dep-missing exception. Pinning this prevents
    over-broad exception coercion in future edits to `_safely_get_parser`.
    """

    def test_runtime_error_from_get_parser_propagates(self):
        with tempfile.TemporaryDirectory() as tmp:
            sample = Path(tmp) / "sample.ts"
            sample.write_text("function hi(){}\n", encoding="utf-8")
            with mock.patch.object(
                tags_mod, "_get_parser",
                side_effect=RuntimeError("grammar corrupt"),
            ):
                with self.assertRaises(RuntimeError):
                    extract_tags(sample)


if __name__ == "__main__":
    unittest.main()
