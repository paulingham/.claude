"""Python 3.9 import-crash regression guard for cost-telemetry modules.

WHY: PEP-604 union annotations (X | None) crash at IMPORT under Python 3.9
(TypeError: unsupported operand type(s) for |). The three cost-telemetry
modules in hooks/_lib/ use runtime-evaluated unions and previously lacked
`from __future__ import annotations` (PEP-563), causing every cost record's
usage_by_model to silently return {} (swallowed by cost-tracker.sh:82
`2>/dev/null || echo '{}'`). CI runs Python 3.14 and never reproduced the
crash — this file is the interpreter-independent backstop that closes the skew.

2am breadcrumb: if usage_by_model is {} across fresh records, OR the PR cost
line stays at the sentinel ($0.00), check that all 3 of transcript_usage.py,
cost_estimator.py, and pr_cost_annotate.py import cleanly under
/usr/bin/python3 (3.9). cost_estimator.py crashes FIRST in the
pr_cost_annotate import chain — fixing only pr_cost_annotate's own annotations
still crashes transitively.

Test strategy:
- A1 (ALWAYS runs): AST static guard — first import after docstring must be
  `from __future__ import annotations` in all 3 files. Interpreter-independent.
- A2-A5 (skip with marker when no <3.10 interpreter found): subprocess tests
  under /usr/bin/python3 to confirm crash/fix at the prod interpreter.
- A6 lives in test_cost_tracker_usage.bats (bats end-to-end).
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import textwrap
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
    after module docstring in all 3 files — runs under any Python version."""

    _FILES = [
        "transcript_usage.py",
        "cost_estimator.py",
        "pr_cost_annotate.py",
    ]

    @pytest.mark.parametrize("filename", _FILES)
    def test_future_annotations_is_first_import_all_three(self, filename: str) -> None:
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
# A2 — transcript_usage imports under prod interpreter
# ---------------------------------------------------------------------------

@_SKIP_RUNTIME
class TestTranscriptUsageImportProdInterpreter:
    """A2: subprocess `import transcript_usage` under /usr/bin/python3 exits 0."""

    def test_transcript_usage_imports_under_prod_interpreter(self) -> None:
        result = subprocess.run(
            [_PROD_INTERP, "-c",
             f"import sys; sys.path.insert(0, {str(HOOKS_LIB)!r}); import transcript_usage"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"transcript_usage import failed under {_PROD_INTERP}:\n{result.stderr}"
        )


# ---------------------------------------------------------------------------
# A3 — cost_estimator imports under prod interpreter
# ---------------------------------------------------------------------------

@_SKIP_RUNTIME
class TestCostEstimatorImportProdInterpreter:
    """A3: subprocess `import cost_estimator` under prod interp exits 0
    (first link in the pr_cost_annotate chain)."""

    def test_cost_estimator_imports_under_prod_interpreter(self) -> None:
        result = subprocess.run(
            [_PROD_INTERP, "-c",
             f"import sys; sys.path.insert(0, {str(HOOKS_LIB)!r}); import cost_estimator"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"cost_estimator import failed under {_PROD_INTERP}:\n{result.stderr}"
        )


# ---------------------------------------------------------------------------
# A4 — pr_cost_annotate imports under prod interpreter (distinct crash path)
# ---------------------------------------------------------------------------

@_SKIP_RUNTIME
class TestPrCostAnnotateImportProdInterpreter:
    """A4: subprocess `import pr_cost_annotate` under prod interp exits 0.

    Distinct crash path: pr_cost_annotate imports cost_estimator (line 26)
    AND transcript_usage (line 27) transitively, PLUS has its own PEP-604
    unions at :152 (_default_transcript) and :158 (_resolve_transcript).
    This test confirms both import legs are fixed.
    """

    def test_pr_cost_annotate_imports_under_prod_interpreter(self) -> None:
        result = subprocess.run(
            [_PROD_INTERP, "-c",
             f"import sys; sys.path.insert(0, {str(HOOKS_LIB)!r}); import pr_cost_annotate"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"pr_cost_annotate import failed under {_PROD_INTERP}:\n{result.stderr}"
        )


# ---------------------------------------------------------------------------
# A5 — happy-path: non-empty usage_by_model under prod interpreter
# ---------------------------------------------------------------------------

_FIXTURE_TRANSCRIPT = textwrap.dedent("""\
    {"type":"assistant","message":{"model":"claude-opus-4-8","usage":{"input_tokens":1000,"output_tokens":200,"cache_read_input_tokens":500,"cache_creation_input_tokens":100}}}
    {"type":"assistant","message":{"model":"claude-sonnet-4-6","usage":{"input_tokens":300,"output_tokens":50,"cache_read_input_tokens":0,"cache_creation_input_tokens":0}}}
    {"type":"assistant","message":{"model":"claude-opus-4-8","usage":{"input_tokens":400,"output_tokens":80,"cache_read_input_tokens":200,"cache_creation_input_tokens":50}}}
""")


@_SKIP_RUNTIME
class TestUsageByModelHappyPathProdInterpreter:
    """A5: subprocess-run transcript_usage.py with 2-model fixture under prod interp
    → non-empty usage_by_model with summed opus input_tokens correct."""

    def test_nonempty_usage_by_model_under_prod_interpreter(self, tmp_path: Path) -> None:
        transcript = tmp_path / "transcript.jsonl"
        transcript.write_text(_FIXTURE_TRANSCRIPT, encoding="utf-8")

        result = subprocess.run(
            [_PROD_INTERP, str(HOOKS_LIB / "transcript_usage.py"), str(transcript)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"transcript_usage.py crashed under {_PROD_INTERP}:\n{result.stderr}"
        )
        data = json.loads(result.stdout.strip())
        assert data, "usage_by_model was empty (crash → {} path still active)"
        # opus total input = 1000 + 400 = 1400
        assert data["claude-opus-4-8"]["input_tokens"] == 1400, (
            f"expected 1400, got {data['claude-opus-4-8']['input_tokens']}"
        )
        assert data["claude-sonnet-4-6"]["input_tokens"] == 300, (
            f"expected 300, got {data['claude-sonnet-4-6']['input_tokens']}"
        )
