#!/usr/bin/env python3
"""Emit one JSONL line to {metrics_dir}/tool-timings.jsonl.

Args (positional, all required, may be empty string):
  metrics_dir  ts  tool  duration_ms  success  agent_role  task_id

Field order: ts, tool, duration_ms, success, agent_role, task_id.
agent_role/task_id are OMITTED when empty (omit-not-null contract).
"""
import json
import os
import sys


def _build_record(ts, tool, duration_ms, success, agent_role, task_id):
    rec = {"ts": ts, "tool": tool, "duration_ms": int(duration_ms),
           "success": success.lower() == "true"}
    if agent_role:
        rec["agent_role"] = agent_role
    if task_id:
        rec["task_id"] = task_id
    return rec


def _append_line(metrics_dir, rec):
    os.makedirs(metrics_dir, exist_ok=True)
    out = os.path.join(metrics_dir, "tool-timings.jsonl")
    with open(out, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def main(argv):
    if len(argv) != 8:
        return 0
    try:
        rec = _build_record(*argv[2:])
    except (TypeError, ValueError):
        return 0
    _append_line(argv[1], rec)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
