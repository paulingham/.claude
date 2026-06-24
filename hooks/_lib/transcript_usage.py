#!/usr/bin/env python3
"""Sum token usage by model from a Claude Code transcript JSONL.

Public API:
    sum_usage_by_model(transcript_path) -> dict[model, dict[field, int]]

Reads the transcript at `transcript_path`, iterates every record, and for
each `assistant` record sums `.message.usage.*` tokens grouped by
`.message.model`.

WHY: The Stop hook already has transcript_path on stdin. This is the
correct read-path for real per-session token totals. stuck-detector.py's
parse_transcript is NOT reused — it filters to post-boundary events and
strips usage (confirmed).

Fail-open: any bad input (missing file, bad JSON, missing fields) is
tolerated — returns {} rather than raising. Mirrors stuck-detector.py's
bare-except discipline.
"""
# WHY: PEP-604 union annotations (X | None) are runtime-evaluated under Python 3.9
# and crash at import with TypeError. This import defers annotation evaluation
# (PEP-563), matching the ~40 other _lib files that use the same pattern.
from __future__ import annotations

import json
import sys
from collections import defaultdict

_USAGE_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
)


def sum_usage_by_model(transcript_path) -> dict:
    """Return per-model summed usage from all assistant records in transcript."""
    try:
        return _sum_from_path(transcript_path)
    except Exception:  # noqa: BLE001 — bad transcript must never wedge Stop
        return {}


def _sum_from_path(transcript_path) -> dict:
    try:
        lines = _read_lines(transcript_path)
    except (OSError, TypeError):
        return {}
    return _sum_lines(lines)
def _read_lines(transcript_path) -> list:
    with open(transcript_path, "r", encoding="utf-8") as fh:
        return [ln.strip() for ln in fh]
def _sum_lines(lines: list) -> dict:
    accumulator: dict = defaultdict(lambda: dict.fromkeys(_USAGE_FIELDS, 0))
    for line in lines:
        _process_line(line, accumulator)
    return dict(accumulator)


def _process_line(line: str, accumulator: dict) -> None:
    if not line:
        return
    record = _parse_json_line(line)
    if record is not None:
        _accumulate_record(record, accumulator)


def _parse_json_line(line: str):
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


def _accumulate_record(record: dict, accumulator: dict) -> None:
    model, usage = _extract_model_usage(record)
    if not model or usage is None:
        return
    for field in _USAGE_FIELDS:
        accumulator[model][field] += int(usage.get(field, 0) or 0)
def _is_assistant(record: dict) -> bool:
    return isinstance(record, dict) and record.get("type") == "assistant"
def _extract_message_fields(message: dict):
    model = message.get("model", "")
    usage = message.get("usage")
    if not model or not isinstance(usage, dict):
        return None, None
    return model, usage
def _extract_model_usage(record: dict):
    if not _is_assistant(record):
        return None, None
    message = record.get("message", {})
    if not isinstance(message, dict):
        return None, None
    return _extract_message_fields(message)
def _resolve_path() -> str | None:
    return sys.argv[1] if len(sys.argv) > 1 else None


def main() -> None:
    """Script entry point: read transcript path from argv[1], print JSON."""
    try:
        print(json.dumps(sum_usage_by_model(_resolve_path())))
    except Exception:  # noqa: BLE001
        print("{}")


if __name__ == "__main__":
    main()
