"""Cross-component contract pin: cost_parse.REQUIRED ⊆ keys emitted by cost-jsonl-emit.py.

B2: pins that the fields cost_parse.py:10 declares as REQUIRED are all present
in every record cost-jsonl-emit.py emits. RED if either side drifts — either
cost_parse.REQUIRED grows a field that cost-jsonl-emit.py doesn't emit, or
cost-jsonl-emit.py drops a field that cost_parse.py requires.

WHY: cost-feed.sh:41-47 emit block is kept (Option B, no deletion) because
eval-model-effectiveness hard-requires agent_role (cost_parse.py:10, cells.py:17)
and the trace fallback is unimplemented. This test locks the shape contract
between producer (cost-jsonl-emit.py) and consumer (cost_parse.py) so a
future careless deletion is caught at test time, not at eval runtime.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS_LIB = REPO_ROOT / "hooks" / "_lib"
EVAL_SKILL_DIR = REPO_ROOT / "skills" / "eval-model-effectiveness"


def _emit_record(tmp_dir: Path) -> dict:
    """Invoke cost-jsonl-emit.py with a realistic payload; return the written record."""
    metrics_dir = str(tmp_dir / "metrics")
    result = subprocess.run(
        [
            sys.executable,
            str(HOOKS_LIB / "cost-jsonl-emit.py"),
            metrics_dir,
            "2026-06-24T00:00:00Z",  # ts
            "test-session-id",        # sid
            "test-pipeline",          # pid
            "software-engineer",      # role
            "claude-opus-4-8",        # model
            "0.0185",                 # cost
            "1000",                   # i (input_tokens)
            "500",                    # o (output_tokens)
            "2000",                   # c (cache_read_input_tokens)
            "10",                     # complexity_budget
            "0",                      # prior_error_count
            "3",                      # graph_depth
            "standard",               # router_decision
        ],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"cost-jsonl-emit.py failed:\n{result.stderr}"
    costs_file = Path(metrics_dir) / "costs.jsonl"
    assert costs_file.exists(), "cost-jsonl-emit.py wrote no record"
    return json.loads(costs_file.read_text(encoding="utf-8").strip())


def _load_cost_parse_required() -> tuple[str, ...]:
    """Import cost_parse.REQUIRED via subprocess to avoid skill deps in test env."""
    result = subprocess.run(
        [
            sys.executable, "-c",
            f"import sys; sys.path.insert(0, {str(EVAL_SKILL_DIR)!r}); "
            "from cost_parse import REQUIRED; print(' '.join(REQUIRED))",
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        pytest.skip(f"cost_parse not importable (missing deps): {result.stderr[:200]}")
    return tuple(result.stdout.strip().split())


class TestCostParseFielsSubsetOfCostFeedEmit:
    """B2: cost_parse.REQUIRED ⊆ keys emitted by cost-jsonl-emit.py."""

    def test_cost_parse_required_fields_subset_of_costfeed_emit(
        self, tmp_path: Path
    ) -> None:
        """All fields in cost_parse.REQUIRED must appear in a record emitted by
        cost-jsonl-emit.py. RED if the emit block is deleted or a required field
        is dropped from the emitter."""
        required = _load_cost_parse_required()
        assert required, "cost_parse.REQUIRED is empty — unexpected"

        record = _emit_record(tmp_path)
        missing = [f for f in required if f not in record]
        assert not missing, (
            f"cost_parse.REQUIRED fields missing from cost-jsonl-emit.py output: "
            f"{missing!r}. REQUIRED={required!r}, record keys={sorted(record)!r}"
        )
