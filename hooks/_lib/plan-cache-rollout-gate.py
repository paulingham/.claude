#!/usr/bin/env python3
"""Slice G — Plan-cache rollout-gate aggregator.

Reads plan-cache.jsonl records across `<metrics-dir>/*/plan-cache.jsonl`
and emits a structured JSON verdict to stdout.

Window selection (plan.md § Slice slice-g-rollout-gate-skill):
  Use the LARGER of last-N=30-pipelines or last-14-days. Pipelines are
  counted by distinct `session_id`. Data is insufficient iff
  `sessions_seen < 30 AND days_span < 14`.

Thresholds (verbatim from plan.md):
  hit_rate                >= 0.10
  pv_pass_rate_on_hit     >= 0.95
  cost_delta              >  0

Definitions:
  hit_rate = hits / (hits + misses_excluding_shadow_mode_reason)
  pv_pass_rate_on_hit = HITs with pv_outcome==PLAN_APPROVED / total HITs
  cost_delta = sum(saved_architect_tokens_estimate) - sum(adapter_cost_tokens)

Verdicts emitted:
  ROLLOUT_GATE_PASS    all three thresholds met
  ROLLOUT_GATE_FAIL    >=1 threshold failed; body cites which
  INSUFFICIENT_DATA    sessions<30 AND days_span<14
"""
import argparse
import datetime as dt
import glob
import json
import os
import sys

HIT_RATE_MIN = 0.10
PV_PASS_RATE_MIN = 0.95
COST_DELTA_MIN = 0  # strict > 0
PIPELINES_FLOOR = 30
DAYS_FLOOR = 14


def _load_records(metrics_dir):
    """Read every <metrics-dir>/*/plan-cache.jsonl line; skip malformed."""
    records = []
    pattern = os.path.join(metrics_dir, "*", "plan-cache.jsonl")
    for path in glob.glob(pattern):
        records.extend(_load_one(path))
    return records


def _load_one(path):
    out = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except (json.JSONDecodeError, ValueError):
                    continue
    except OSError:
        return []
    return out


def _parse_ts(record):
    raw = record.get("timestamp", "")
    try:
        return dt.datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=dt.timezone.utc
        )
    except (ValueError, TypeError):
        return None


def _days_span(records, now):
    timestamps = [t for t in (_parse_ts(r) for r in records) if t is not None]
    if not timestamps:
        return 0.0
    oldest = min(timestamps)
    return (now - oldest).total_seconds() / 86400.0


def _data_sufficient(sessions_seen, days_span):
    return sessions_seen >= PIPELINES_FLOOR or days_span >= DAYS_FLOOR


def _compute_metrics(records):
    hits = [r for r in records if r.get("verdict") == "PLAN_CACHE_HIT"]
    real_misses = [
        r for r in records
        if r.get("verdict") == "PLAN_CACHE_MISS"
        and r.get("miss_reason") != "shadow-mode"
    ]
    denom = len(hits) + len(real_misses)
    hit_rate = (len(hits) / denom) if denom else 0.0
    approved = sum(1 for r in hits if r.get("pv_outcome") == "PLAN_APPROVED")
    pv_pass_rate = (approved / len(hits)) if hits else 0.0
    saved = sum(int(r.get("saved_architect_tokens_estimate") or 0) for r in hits)
    spent = sum(int(r.get("adapter_cost_tokens") or 0) for r in hits)
    return {
        "hits": len(hits),
        "real_misses": len(real_misses),
        "hit_rate": round(hit_rate, 4),
        "pv_pass_rate_on_hit": round(pv_pass_rate, 4),
        "cost_delta": saved - spent,
    }


def _grade(metrics):
    failed = []
    if metrics["hit_rate"] < HIT_RATE_MIN:
        failed.append(f"hit_rate={metrics['hit_rate']} < 0.10")
    if metrics["pv_pass_rate_on_hit"] < PV_PASS_RATE_MIN:
        failed.append(
            f"pv_pass_rate_on_hit={metrics['pv_pass_rate_on_hit']} < 0.95"
        )
    if metrics["cost_delta"] <= COST_DELTA_MIN:
        failed.append(f"cost_delta={metrics['cost_delta']} <= 0")
    return failed


def _emit(payload):
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--metrics-dir",
        default=os.environ.get(
            "CLAUDE_HOOK_LOG_DIR",
            os.path.expanduser("~/.claude/metrics"),
        ),
    )
    args = parser.parse_args(argv[1:])
    records = _load_records(args.metrics_dir)
    sessions = {r.get("session_id") for r in records if r.get("session_id")}
    sessions_seen = len(sessions)
    days_span = _days_span(records, dt.datetime.now(dt.timezone.utc))
    if not _data_sufficient(sessions_seen, days_span):
        _emit({
            "verdict": "INSUFFICIENT_DATA",
            "sessions_seen": sessions_seen,
            "days_span": round(days_span, 2),
            "floor": {"pipelines": PIPELINES_FLOOR, "days": DAYS_FLOOR},
        })
        return 0
    metrics = _compute_metrics(records)
    failed = _grade(metrics)
    payload = {
        "verdict": "ROLLOUT_GATE_PASS" if not failed else "ROLLOUT_GATE_FAIL",
        "sessions_seen": sessions_seen,
        "days_span": round(days_span, 2),
        "thresholds": {
            "hit_rate_min": HIT_RATE_MIN,
            "pv_pass_rate_min": PV_PASS_RATE_MIN,
            "cost_delta_min_strict": COST_DELTA_MIN,
        },
        "metrics": metrics,
        "failed_thresholds": failed,
    }
    _emit(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
