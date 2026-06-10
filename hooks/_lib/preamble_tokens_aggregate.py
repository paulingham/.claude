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
                    preamble_tokens is a non-negative int (bool excluded).
    dropped_lines = count of lines that are (a) malformed JSON, OR
                    (b) parse as event=="session_end" but preamble_tokens
                    is absent, negative, not an int, or a bool.
    (Non-session_end lines are silently skipped regardless of whether they
     carry preamble_tokens — structural skip, NOT dropped.)

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
        tag = _classify_record(record)
        if tag == "valid_session_end":
            total_preamble_tokens += record["preamble_tokens"]
            session_count += 1
        elif tag == "corrupt_session_end":
            dropped_lines += 1

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


def _classify_record(record: dict) -> str:
    """Classify a parsed record into 'valid_session_end', 'corrupt_session_end', or 'skip'."""
    if not isinstance(record, dict) or record.get("event") != "session_end":
        return "skip"
    if _is_valid_preamble_tokens(record.get("preamble_tokens")):
        return "valid_session_end"
    return "corrupt_session_end"


def _is_valid_preamble_tokens(pt: object) -> bool:
    """Return True for a non-negative int that is not a bool."""
    return isinstance(pt, int) and not isinstance(pt, bool) and pt >= 0


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
