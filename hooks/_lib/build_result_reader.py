#!/usr/bin/env python3
"""Fail-closed reader for build-result.json (stall-fix completion signal).

Mirrors hooks/_lib/resolve-freshness.py::_load_evidence. The orchestrator
uses this as the source of truth for build completion instead of parsing
agent prose. This is a MITIGATION for an upstream Claude Code
background-agent loop-scheduling gap (issues #61547/#44783), not a
root-cause fix: a subagent's loop can go idle after a clean tool_result
and never advance to emit its prose report. The signal is never lost --
the loop just never reaches the point where it would emit it -- so a
durable file written before that point gives the orchestrator a
completion signal regardless.

SAFETY: never returns COMPLETE for an absent, unreadable, or malformed
file (Iron Law 8 — a gate that cannot evaluate its condition fails closed).
"""
from __future__ import annotations

import json
import os

REQUIRED_FIELDS = ("verdict", "branch", "head_sha")
VALID_VERDICTS = {"BUILD_COMPLETE", "BUILD_FAILED"}
ERROR_STATUS = {"missing": "MISSING", "parse_error": "CORRUPT"}


def _result_path(state_dir_abs, task_id):
    return os.path.join(state_dir_abs, task_id, "build-result.json")

# Returns (dict_or_none, error_code_or_none); mirrors resolve-freshness._load_evidence.
def _load(path):
    try:
        with open(path) as f:
            return json.load(f), None
    except FileNotFoundError:
        return None, "missing"
    except (OSError, json.JSONDecodeError):
        return None, "parse_error"

def _has_required_fields(result):
    return all(field in result for field in REQUIRED_FIELDS)

def _completed_fields(result):
    fields = ("branch", "head_sha", "base_sha", "green", "generated_at")
    completed = {name: result.get(name) for name in fields}
    completed["status"] = "COMPLETE"
    return completed

def _classify(result):
    if not _has_required_fields(result) or result.get("verdict") not in VALID_VERDICTS:
        return {"status": "CORRUPT"}
    if result["verdict"] == "BUILD_FAILED":
        return {"status": "FAILED", "unresolved": result.get("unresolved", [])}
    return _completed_fields(result)

def read_build_result(state_dir_abs, task_id):
    """Read build-result.json under state_dir_abs/task_id. Never raises."""
    path = _result_path(state_dir_abs, task_id)
    result, error = _load(path)
    if error is not None:
        return {"status": ERROR_STATUS[error]}
    return _classify(result)

if __name__ == "__main__":
    import sys
    state_dir = sys.argv[1] if len(sys.argv) > 1 else ""
    task = sys.argv[2] if len(sys.argv) > 2 else ""
    print(json.dumps(read_build_result(state_dir, task)))
