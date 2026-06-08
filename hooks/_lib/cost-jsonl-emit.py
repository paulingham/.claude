#!/usr/bin/env python3
"""Append one costs.jsonl record (cost-feed.sh SubagentStop producer).

Extracted from cost-feed.sh so the hook entry-point stays under its ≤50-LOC cap
and every bash helper stays ≤5 lines (cost-helpers.sh contract). Mirrors the
sibling cache-jsonl-emit.py shape. Fail-open: any error exits 0 with no write.

Usage:
  cost-jsonl-emit.py <metrics_dir> <ts> <sid> <pid> <role> <model> \
      <cost> <i> <o> <c> <complexity_budget> <prior_error_count> \
      <graph_depth> <router_decision>

Numeric-ish args (cost/i/o/c, complexity_budget, graph_depth) are passed as
strings and coerced; the JSON-null sentinels "null" become real null.
"""
import json
import os
import sys


def _num(v, default=0):
    if v is None or v == "" or v == "null":
        return None if v == "null" else default
    try:
        f = float(v)
        return int(f) if f.is_integer() else f
    except (TypeError, ValueError):
        return default


def main(argv):
    try:
        (metrics_dir, ts, sid, pid, role, model, cost, i, o, c,
         cb, pec, gd, rd) = argv[1:15]
    except ValueError:
        return 0
    record = {
        "timestamp": ts, "session_id": sid, "pipeline_id": pid,
        "agent_role": role, "model": model,
        "total_cost_usd": _num(cost), "input_tokens": _num(i),
        "output_tokens": _num(o), "cached_tokens": _num(c),
        "rate_version": "opus-4-7-2026-04",
        "complexity_budget": _num(cb), "prior_error_count": _num(pec, 0),
        "graph_depth": _num(gd), "router_decision": rd,
    }
    try:
        os.makedirs(metrics_dir, exist_ok=True)
        with open(os.path.join(metrics_dir, "costs.jsonl"), "a",
                  encoding="utf-8") as fh:
            fh.write(json.dumps(record, separators=(",", ":")) + "\n")
    except OSError:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
