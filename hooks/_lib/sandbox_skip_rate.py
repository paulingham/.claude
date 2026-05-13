"""Aggregate sandbox-verify skip-rate across per-session JSONL logs.

`aggregate_skip_rate(metrics_root)` walks
`metrics_root/*/sandbox-verify-skips.jsonl`, counts reasons, and
returns the canonical dict consumed by `skills/cost-report/SKILL.md`
Step 5.

Return shape (Tier-0 C4):

    {
        "reasons": dict[str, int],       # per-reason invocation counts
        "total_invocations": int,        # all JSONL lines (sum + dropped)
        "skip_rate": float,              # sum(reasons) / total_invocations
        "dropped_lines": int,            # malformed / missing-reason lines
    }

Identity invariant (C4):
    total_invocations == sum(reasons.values()) + dropped_lines

Empty metrics_root, non-existent paths, malformed JSONL lines, and
records missing the `reason` field are all tolerated — the function
never raises.

NOTE on `total_invocations` semantics: this is the per-JSONL-line
count, NOT a per-session de-dup. Pipelines that retry sandbox-verify
inside a single round may emit multiple skip lines; each contributes
to `total_invocations`. Per the Story 4 pre-mortem, the future
enhancement is `unique_pipelines` as a separate field — out of scope
for this slice.
"""
from __future__ import annotations

import json
from pathlib import Path


_SKIPS_FILENAME = "sandbox-verify-skips.jsonl"


def aggregate_skip_rate(metrics_root: Path) -> dict:
    """Return the canonical aggregate dict for `metrics_root/*/skips.jsonl`."""
    metrics_root = Path(metrics_root)
    reasons: dict[str, int] = {}
    dropped_lines = 0
    total_invocations = 0

    if not metrics_root.exists():
        return _empty_result()

    for path in _discover_skip_files(metrics_root):
        for record in _iter_records(path):
            total_invocations += 1
            if record is _DROPPED:
                dropped_lines += 1
                continue
            reason = record.get("reason") if isinstance(record, dict) else None
            if not reason or not isinstance(reason, str):
                dropped_lines += 1
                continue
            reasons[reason] = reasons.get(reason, 0) + 1

    skip_rate = _compute_rate(sum(reasons.values()), total_invocations)
    return {
        "reasons": reasons,
        "total_invocations": total_invocations,
        "skip_rate": skip_rate,
        "dropped_lines": dropped_lines,
    }


def _empty_result() -> dict:
    return {
        "reasons": {},
        "total_invocations": 0,
        "skip_rate": 0.0,
        "dropped_lines": 0,
    }


def _discover_skip_files(metrics_root: Path):
    """Yield `metrics_root/<session>/sandbox-verify-skips.jsonl` files.

    Only walks one level deep — each session has its own subdirectory.
    """
    for child in sorted(metrics_root.iterdir()):
        if not child.is_dir():
            continue
        candidate = child / _SKIPS_FILENAME
        if candidate.is_file():
            yield candidate


# Sentinel distinguishing "line malformed" from "valid JSON dict".
_DROPPED = object()


def _iter_records(path: Path):
    """Yield one record per non-blank line; `_DROPPED` on parse error."""
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                yield _DROPPED
                continue
            yield record


def _compute_rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator
