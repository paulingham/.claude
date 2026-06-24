"""Python 3.9 import-crash regression guard for scratchpad and stuck-detection modules.

WHY: PEP-604 union annotations (X | None) crash at IMPORT under Python 3.9
(TypeError: unsupported operand type(s) for |). Four modules in hooks/_lib/
use runtime-evaluated unions and previously lacked `from __future__ import
annotations` (PEP-563), causing crashes in production hooks:

  stuck_patterns <- stuck-detector.py <- hooks/stuck-guard.sh (live hook)
  scratchpad_frontmatter <- scratchpad_finding_parser <- scratchpad_diff

CI runs Python 3.14 and never reproduced the crash — this file is the
interpreter-independent backstop that closes the skew.

2am breadcrumb: if stuck-guard.sh silently fails, OR scratchpad findings are
not surfaced to the planning agent, check that all 4 of scratchpad_diff.py,
scratchpad_finding_parser.py, scratchpad_frontmatter.py, and stuck_patterns.py
import cleanly under /usr/bin/python3 (3.9).

Test strategy:
- A1 (ALWAYS runs): AST static guard — first import after docstring must be
  `from __future__ import annotations` in all 4 files. Interpreter-independent.
- A2-A5 (skip with marker when no <3.10 interpreter found): subprocess tests
  under /usr/bin/python3 to confirm crash/fix at the prod interpreter.
  Importing scratchpad_diff (top of chain) transitively covers
  scratchpad_finding_parser and scratchpad_frontmatter — but each is also
  asserted directly.
"""
from __future__ import annotations

import ast
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS_LIB = REPO_ROOT / "hooks" / "_lib"


# ---------------------------------------------------------------------------
# Interpreter resolution (A2-A5 gating)
# ---------------------------------------------------------------------------

def _resolve_prod_interpreter() -> str | None:
    """Return /usr/bin/python3 iff it exists AND reports sys.version_info < (3, 10)."""
    candidate = "/usr/bin/python3"
    if not os.path.isfile(candidate):
        return None
    result = subprocess.run(
        [candidate, "-c",
         "import sys; print(1 if sys.version_info < (3, 10) else 0)"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None
    return candidate if result.stdout.strip() == "1" else None


_PROD_INTERP = _resolve_prod_interpreter()
_SKIP_RUNTIME = pytest.mark.skipif(
    _PROD_INTERP is None,
    reason="skip: no <3.10 interpreter available; static guard A1 still gates",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _first_import_node(source_path: Path) -> ast.stmt | None:
    """Return the first import statement (Import or ImportFrom) in the file, by lineno."""
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    import_nodes = [
        n for n in ast.walk(tree)
        if isinstance(n, (ast.Import, ast.ImportFrom))
    ]
    if not import_nodes:
        return None
    return min(import_nodes, key=lambda n: n.lineno)


def _is_future_annotations(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.ImportFrom)
        and node.module == "__future__"
        and any(alias.name == "annotations" for alias in node.names)
    )


# ---------------------------------------------------------------------------
# A1 — static guard (ALWAYS runs, interpreter-independent)
# ---------------------------------------------------------------------------

class TestFutureAnnotationsStaticGuard:
    """A1: AST assert that from __future__ import annotations is FIRST import
    after module docstring in all 4 files — runs under any Python version."""

    _FILES = [
        "scratchpad_diff.py",
        "scratchpad_finding_parser.py",
        "scratchpad_frontmatter.py",
        "stuck_patterns.py",
    ]

    @pytest.mark.parametrize("filename", _FILES)
    def test_future_annotations_is_first_import(self, filename: str) -> None:
        """A1: first import statement must be `from __future__ import annotations`."""
        path = HOOKS_LIB / filename
        assert path.exists(), f"expected {path} to exist"
        node = _first_import_node(path)
        assert node is not None, (
            f"{filename}: no import statements found"
        )
        assert _is_future_annotations(node), (
            f"{filename}: first import at line {node.lineno} is not "
            f"`from __future__ import annotations`"
        )


# ---------------------------------------------------------------------------
# A2 — scratchpad_frontmatter imports under prod interpreter
# ---------------------------------------------------------------------------

@_SKIP_RUNTIME
class TestScratchpadFrontmatterImportProdInterpreter:
    """A2: subprocess `import scratchpad_frontmatter` under /usr/bin/python3 exits 0."""

    def test_scratchpad_frontmatter_imports_under_prod_interpreter(self) -> None:
        result = subprocess.run(
            [_PROD_INTERP, "-c",
             f"import sys; sys.path.insert(0, {str(HOOKS_LIB)!r}); import scratchpad_frontmatter"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"scratchpad_frontmatter import failed under {_PROD_INTERP}:\n{result.stderr}"
        )


# ---------------------------------------------------------------------------
# A3 — scratchpad_finding_parser imports under prod interpreter
# ---------------------------------------------------------------------------

@_SKIP_RUNTIME
class TestScratchpadFindingParserImportProdInterpreter:
    """A3: subprocess `import scratchpad_finding_parser` under prod interp exits 0."""

    def test_scratchpad_finding_parser_imports_under_prod_interpreter(self) -> None:
        result = subprocess.run(
            [_PROD_INTERP, "-c",
             f"import sys; sys.path.insert(0, {str(HOOKS_LIB)!r}); import scratchpad_finding_parser"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"scratchpad_finding_parser import failed under {_PROD_INTERP}:\n{result.stderr}"
        )


# ---------------------------------------------------------------------------
# A4 — scratchpad_diff imports under prod interpreter (top of import chain)
# ---------------------------------------------------------------------------

@_SKIP_RUNTIME
class TestScratchpadDiffImportProdInterpreter:
    """A4: subprocess `import scratchpad_diff` under prod interp exits 0.

    scratchpad_diff is the top of the chain: it imports scratchpad_finding_parser
    which imports scratchpad_frontmatter. Importing scratchpad_diff transitively
    covers all three scratchpad modules.
    """

    def test_scratchpad_diff_imports_under_prod_interpreter(self) -> None:
        result = subprocess.run(
            [_PROD_INTERP, "-c",
             f"import sys; sys.path.insert(0, {str(HOOKS_LIB)!r}); import scratchpad_diff"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"scratchpad_diff import failed under {_PROD_INTERP}:\n{result.stderr}"
        )


# ---------------------------------------------------------------------------
# A5 — stuck_patterns imports under prod interpreter
# ---------------------------------------------------------------------------

@_SKIP_RUNTIME
class TestStuckPatternsImportProdInterpreter:
    """A5: subprocess `import stuck_patterns` under prod interp exits 0."""

    def test_stuck_patterns_imports_under_prod_interpreter(self) -> None:
        result = subprocess.run(
            [_PROD_INTERP, "-c",
             f"import sys; sys.path.insert(0, {str(HOOKS_LIB)!r}); import stuck_patterns"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"stuck_patterns import failed under {_PROD_INTERP}:\n{result.stderr}"
        )
