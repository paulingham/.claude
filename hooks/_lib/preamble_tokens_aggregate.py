"""Aggregate measured preamble_tokens across per-session costs.jsonl records.

`aggregate_preamble_tokens(metrics_root)` reads
`metrics_root/costs.jsonl`, counts only `session_end` records that
carry a non-negative integer `preamble_tokens` field, and returns the
canonical dict consumed by `skills/cost-report/SKILL.md`
Step 5-bis (## Preamble Tokens (MEASURED)).

The preamble_tokens values are MEASURED per-session at session_end by
`hooks/cost-tracker.sh` via `hooks/_lib/preamble-tokens-emit.py`.

Return shape:

    {
        "total_preamble_tokens": int,  # sum of preamble_tokens across valid records
        "session_count": int,          # count of valid session_end records
        "dropped_lines": int,          # malformed / missing-field lines
    }

Identity invariant:
    session_count = count of lines where event=="session_end" AND
                    preamble_tokens is a non-negative int.
    dropped_lines = count of lines that are malformed JSON or that parse
                    as non-session_end AND preamble_tokens is absent/invalid.
    (Non-session_end lines with valid preamble_tokens are silently skipped;
     they are not counted in dropped_lines as they are structurally valid.)

NOTE on file location: `cost-tracker.sh` writes a single flat file at
`metrics/costs.jsonl` (not per-session subdirectories). This helper reads
that flat file directly; `metrics_root` is the `metrics/` directory.

Empty metrics_root, non-existent paths, missing `costs.jsonl`, malformed
JSONL lines, and records missing required fields are all tolerated — the
function never raises.
"""
from __future__ import annotations

import json
from pathlib import Path


_COSTS_FILENAME = "costs.jsonl"


def aggregate_preamble_tokens(metrics_root: Path) -> dict:
    """Return the canonical aggregate dict for `metrics_root/costs.jsonl`."""
    metrics_root = Path(metrics_root)
    costs_file = metrics_root / _COSTS_FILENAME

    if not costs_file.is_file():
        return _empty_result()

    total_preamble_tokens = 0
    session_count = 0
    dropped_lines = 0

    for record in _iter_records(costs_file):
        if record is _DROPPED:
            dropped_lines += 1
            continue
        if not _is_valid_session_end(record):
            continue
        total_preamble_tokens += record["preamble_tokens"]
        session_count += 1

    return {
        "total_preamble_tokens": total_preamble_tokens,
        "session_count": session_count,
        "dropped_lines": dropped_lines,
    }


def _empty_result() -> dict:
    return {
        "total_preamble_tokens": 0,
        "session_count": 0,
        "dropped_lines": 0,
    }


def _is_valid_session_end(record: dict) -> bool:
    """Return True when record is a session_end with a non-negative int preamble_tokens."""
    if not isinstance(record, dict):
        return False
    if record.get("event") != "session_end":
        return False
    pt = record.get("preamble_tokens")
    return isinstance(pt, int) and pt >= 0


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
