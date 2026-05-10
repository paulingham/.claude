"""Slice B render acceptance tests.

ACs covered:
- AC11 — token-budget enforcement, lowest-ranked symbols truncated first.
- AC11-bis — `build(..., max_files=N)` walk truncation prioritised by
  alphabetical sort of repo-relative path; stderr warning emitted.
- AC13 — empty repo returns documented one-line empty-state marker.
"""
from __future__ import annotations

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from codebase_map import build as build_mod  # noqa: E402
from codebase_map import graph as graph_mod  # noqa: E402
from codebase_map import render as render_mod  # noqa: E402
from codebase_map.tags_types import Tag  # noqa: E402


def _tag(file: str, kind: str, name: str) -> Tag:
    return Tag(file=file, mtime=0.0, kind=kind, name=name,
               line=1, col=0, lang="python")


class AC11RenderWithinBudget(unittest.TestCase):
    """`render(graph, scores, budget=N)` produces markdown ≤ budget tokens.

    Truncation cuts the lowest-ranked symbols first.
    """

    def test_ac11_render_within_budget(self) -> None:
        # 20 files, ranked descending. Budget will force truncation.
        tags = []
        for i in range(20):
            tags.append(_tag(f"file_{i:02d}.py", "def", f"sym_{i}"))
        graph = graph_mod.build_graph(tags)
        # Highest score on file_00, lowest on file_19.
        scores = {f"file_{i:02d}.py": (20 - i) * 0.05 for i in range(20)}
        budget = 64
        out = render_mod.render(graph, scores, budget=budget)

        self.assertLessEqual(render_mod.count_tokens(out), budget)
        # Highest-ranked file present
        self.assertIn("file_00.py", out)
        # Lowest-ranked file pruned (truncation drops lowest first)
        self.assertNotIn("file_19.py", out)


class AC11bisMaxFilesTruncationAlphabetical(unittest.TestCase):
    """`build(..., max_files=N)` truncates walk to alphabetically-first N
    repo-relative paths AND emits one stderr warning line.
    """

    def test_ac11bis_max_files_truncation_alphabetical(self) -> None:
        # Generate 100 .py filenames with zero-padded numeric suffixes
        # so the alphabetical sort is unambiguous and stable. The first
        # 10 alphabetically are guaranteed to be ``f_000.py`` …
        # ``f_009.py`` regardless of OS filesystem traversal order.
        names = [f"f_{i:03d}.py" for i in range(100)]
        first_ten_expected = sorted(names)[:10]

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            for name in names:
                # tiny but non-empty Python file with one def
                (repo / name).write_text(
                    f"def f_{name.replace('.','_')}():\n    pass\n"
                )
            cache = Path(tmp) / "cache.sqlite"

            err = io.StringIO()
            with redirect_stderr(err):
                out = build_mod.build(
                    repo_root=repo,
                    cache_dir=cache,
                    max_files=10,
                )

            # Warning emitted exactly once
            err_text = err.getvalue()
            warning_lines = [
                ln for ln in err_text.splitlines()
                if ln.startswith("codebase-map: truncated walk at max_files=10")
            ]
            self.assertEqual(
                len(warning_lines), 1,
                f"expected one truncation warning, got: {err_text!r}",
            )
            self.assertIn(" (100 files seen)", warning_lines[0])

            # The output must reference only the alphabetically-first 10
            for name in first_ten_expected:
                self.assertIn(
                    name, out,
                    f"expected {name} in render output (alphabetical "
                    f"first 10), got: {out!r}",
                )
            # And must NOT reference any of the dropped names
            for name in sorted(names)[10:]:
                self.assertNotIn(
                    name, out,
                    f"file {name} should have been truncated (rank > 10)",
                )


class AC13EmptyRepoEmptyState(unittest.TestCase):
    """A repo with zero supported source files returns a documented empty-state digest.

    One-line marker, NOT an exception.
    """

    def test_ac13_empty_repo_empty_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "empty_repo"
            repo.mkdir()
            # Place a non-source file to confirm it is filtered out.
            (repo / "README.md").write_text("# nothing\n")
            cache = Path(tmp) / "cache.sqlite"

            out = build_mod.build(repo_root=repo, cache_dir=cache)

            # One-line marker
            stripped = out.strip()
            self.assertIn("codebase-map: empty", stripped)
            self.assertEqual(
                len(stripped.splitlines()), 1,
                f"empty-state digest must be a single line, got: {out!r}",
            )


if __name__ == "__main__":
    unittest.main()
