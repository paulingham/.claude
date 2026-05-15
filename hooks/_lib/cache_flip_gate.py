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

import datetime
import json
import statistics
import sys
from pathlib import Path

_FLIP_THRESHOLD = 0.70
_MIN_PASS_N = 100
_MIN_GRADE_N = 30
_WINDOW_DAYS = 30


def _parse_ts(value: object) -> datetime.datetime | None:
    """Parse an ISO 8601 timestamp; return None if missing/malformed."""
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def _mtime_within_window(path: Path, cutoff_epoch: float) -> bool:
    """True iff the file's mtime is at/after cutoff (cheap pre-filter)."""
    try:
        return path.stat().st_mtime >= cutoff_epoch
    except OSError:
        return False


def _ratio_if_in_window(line: str, cutoff: datetime.datetime,
                       source: Path) -> float | None:
    """Decode one JSONL line; return read_ratio iff in window, else None."""
    try:
        record = json.loads(line)
    except json.JSONDecodeError:
        return None
    ts = _parse_ts(record.get("timestamp"))
    if ts is None:
        print(f"cache_flip_gate: skipping record without "
              f"parseable timestamp in {source}", file=sys.stderr)
        return None
    if ts < cutoff:
        return None
    ratio = record.get("read_ratio")
    return float(ratio) if isinstance(ratio, (int, float)) else None


def _collect_from_file(jsonl: Path, cutoff: datetime.datetime) -> list[float]:
    """Yield in-window read_ratios from a single cache.jsonl file."""
    out: list[float] = []
    for raw in jsonl.read_text().splitlines():
        line = raw.strip()
        if not line:
            continue
        ratio = _ratio_if_in_window(line, cutoff, jsonl)
        if ratio is not None:
            out.append(ratio)
    return out


def _collect_ratios(metrics_root: Path) -> list[float]:
    """Glob cache.jsonl records under metrics_root within the 30-day window.

    Two-stage filter: file mtime pre-filter, then per-record ISO 8601
    `timestamp` field. Records with missing/malformed timestamps are
    skipped and logged to stderr.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    cutoff = now - datetime.timedelta(days=_WINDOW_DAYS)
    cutoff_epoch = cutoff.timestamp()
    ratios: list[float] = []
    for jsonl in metrics_root.glob("*/cache.jsonl"):
        if not _mtime_within_window(jsonl, cutoff_epoch):
            continue
        ratios.extend(_collect_from_file(jsonl, cutoff))
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
