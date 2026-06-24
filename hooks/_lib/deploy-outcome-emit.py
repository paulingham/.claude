#!/usr/bin/env python3
"""Emit one deploy_outcome JSONL line to <base_dir>/observations.jsonl.

Args (positional): script base_dir timestamp pipeline_id outcome environment
Returns 0 on every path (advisory — hook MUST NOT block).
Outcome ∉ VALID_OUTCOMES is stored as <unknown> (attacker-input guard).
"""
import json
import os
import sys

VALID_OUTCOMES = frozenset(
    {"DEPLOYED", "DEPLOY_FAILED", "ROLLED_BACK", "AUTO_ROLLBACK"}
)
_RECORD_TYPE = "deploy_outcome"


def _cap(value: str, limit: int = 1024) -> str:
    return value[:limit]


def _safe_outcome(raw: str) -> str:
    return raw if raw in VALID_OUTCOMES else "<unknown>"


def _record_fields(pipeline_id: str, outcome: str, environment: str) -> dict:
    return {"pipeline_id": _cap(pipeline_id), "outcome": _safe_outcome(outcome), "environment": _cap(environment)}


def build_record(pipeline_id: str, outcome: str, environment: str, timestamp: str) -> dict:
    base = {"record_type": _RECORD_TYPE, "timestamp": timestamp}
    base.update(_record_fields(pipeline_id, outcome, environment))
    return base


def _open_nofollow(path: str) -> int:
    # WHY: O_NOFOLLOW refuses symlinked targets — mirrors intake-fingerprint-emit
    # to prevent attacker-planted symlinks redirecting writes to sensitive files.
    return os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o644)


def _write_fd(fd: int, record: dict) -> None:
    try:
        os.write(fd, (json.dumps(record) + "\n").encode("utf-8"))
    finally:
        os.close(fd)


def append_jsonl(path: str, record: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    _write_fd(_open_nofollow(path), record)


def _emit(base_dir: str, record: dict) -> None:
    path = os.path.join(base_dir, "observations.jsonl")
    try:
        append_jsonl(path, record)
    except OSError:
        pass


def main(argv: list) -> int:
    if len(argv) != 6:
        return 0
    base_dir, timestamp, pipeline_id, outcome, environment = argv[1:6]
    _emit(base_dir, build_record(pipeline_id, outcome, environment, timestamp))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
