"""Cache-flip-gate — evaluates 30-day P50 read_ratio against flip threshold.

Inputs: directory containing per-session subdirectories with `cache.jsonl`
records (one record per spawn with `read_ratio` field).

Verdicts:
  - CACHE_FLIP_GATE_PASS: P50 >= 0.70 AND n >= 100
  - CACHE_FLIP_GATE_HOLD: P50 < 0.70 (and n >= 30)
  - CACHE_FLIP_GATE_INSUFFICIENT_DATA: n < 30

Polarity: info or success only — never gates a pipeline phase. Operator-invoked.
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

_FLIP_THRESHOLD = 0.70
_MIN_PASS_N = 100
_MIN_GRADE_N = 30


def _collect_ratios(metrics_root: Path) -> list[float]:
    """Glob all cache.jsonl records under metrics_root, return read_ratios."""
    ratios: list[float] = []
    for jsonl in metrics_root.glob("*/cache.jsonl"):
        for line in jsonl.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            ratio = record.get("read_ratio")
            if isinstance(ratio, (int, float)):
                ratios.append(float(ratio))
    return ratios


def _classify(ratios: list[float]) -> dict:
    n = len(ratios)
    if n < _MIN_GRADE_N:
        return {"verdict": "CACHE_FLIP_GATE_INSUFFICIENT_DATA",
                "n_observations": n, "p50": None}
    p50 = statistics.median(ratios)
    if p50 >= _FLIP_THRESHOLD and n >= _MIN_PASS_N:
        verdict = "CACHE_FLIP_GATE_PASS"
    else:
        verdict = "CACHE_FLIP_GATE_HOLD"
    return {"verdict": verdict, "n_observations": n, "p50": p50}


def evaluate(metrics_root: Path) -> dict:
    """Public entry point. Returns dict with `verdict`, `n_observations`, `p50`."""
    return _classify(_collect_ratios(metrics_root))
