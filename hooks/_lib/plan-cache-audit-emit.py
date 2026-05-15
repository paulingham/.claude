#!/usr/bin/env python3
"""Emit / update plan-cache.jsonl records.

Two invocation modes (mode arg is positional):

  lookup  metrics_dir timestamp task_id session_id verdict cache_key
          miss_reason adapter_tokens
            -> appends one record with all 9 REQUIRED_KEYS to
               metrics_dir/plan-cache.jsonl.

  pv      metrics_dir session_id pv_verdict
            -> rewrites the most recent record in
               metrics_dir/plan-cache.jsonl whose pv_outcome is unset,
               setting pv_outcome = pv_verdict.

Returns 0 on every path (advisory contract — hook MUST NOT block).
REQUIRED_KEYS (plan.md § Slice slice-e-audit-and-measurement):
  task_id, cache_key, verdict, adapter_cost_tokens, miss_reason,
  hit_template_path, hit_count_after, pv_outcome, session_id.

Slice-G adds a 10th forensic key — `saved_architect_tokens_estimate` —
required by `hooks/_lib/plan-cache-rollout-gate.py` cost_delta computation.
Set to SAVED_TOKENS_PER_HIT (10000) on HIT, 0 otherwise.
"""
import json
import os
import re
import sys

PENDING_PV = "<pending>"
SAVED_TOKENS_PER_HIT = 10000  # Slice G cost_delta input; conservative estimate
# of recon+architect token spend skipped on HIT path. Subject to revision
# after first 30-pipeline measurement window (plan.md § Slice slice-g).


def _read_template_metadata(project_hash, cache_key):
    """Best-effort lookup of hit_template_path + hit_count_after.

    Returns (template_path_or_empty, hit_count_after_int).
    hit_count_after is the post-increment count seen in the template
    frontmatter at audit time. We DO NOT mutate the template here;
    Slice C's _plan_cache_finalize owns mutation.
    """
    if not cache_key:
        return "", 0
    home = os.path.expanduser("~")
    template = os.path.join(home, "learning", project_hash, "plans", f"{cache_key}.md")
    if not os.path.isfile(template):
        return "", 0
    try:
        with open(template, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return "", 0
    match = re.search(r"^hit_count:\s*(\d+)", text, re.MULTILINE)
    count = int(match.group(1)) if match else 0
    return template, count


def _resolve_project_hash():
    """env-first project hash (mirrors observation-capture.sh:30-38)."""
    return os.environ.get("CLAUDE_PROJECT_HASH") or "default"


def _build_record(argv):
    """Compose the 9-key record for one /plan-cache-lookup invocation."""
    (_metrics_dir, ts, task_id, session_id, verdict, cache_key,
     miss_reason, adapter_tokens) = argv[2:10]
    try:
        tokens_numeric = int(adapter_tokens) if adapter_tokens else 0
    except (TypeError, ValueError):
        tokens_numeric = 0
    project_hash = _resolve_project_hash()
    template_path, hit_count = _read_template_metadata(project_hash, cache_key)
    saved = SAVED_TOKENS_PER_HIT if verdict == "PLAN_CACHE_HIT" else 0
    return {
        "task_id": task_id or "<unknown>",
        "cache_key": cache_key or "",
        "verdict": verdict or "<unknown>",
        "adapter_cost_tokens": tokens_numeric,
        "miss_reason": miss_reason or "",
        "hit_template_path": template_path,
        "hit_count_after": hit_count,
        "pv_outcome": PENDING_PV,
        "session_id": session_id or "<unknown>",
        "timestamp": ts,
        "saved_architect_tokens_estimate": saved,
    }


def _append_jsonl(path, record):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    fd = os.open(path, flags, 0o644)
    try:
        os.write(fd, (json.dumps(record) + "\n").encode("utf-8"))
    finally:
        os.close(fd)


def _writeback_pv(jsonl_path, pv_verdict):
    """Find most recent record with pv_outcome=PENDING_PV, set pv_outcome."""
    if not os.path.isfile(jsonl_path):
        return
    with open(jsonl_path, "r", encoding="utf-8") as f:
        lines = [ln for ln in f.read().splitlines() if ln.strip()]
    target_index = _find_last_pending(lines)
    if target_index is None:
        return
    record = json.loads(lines[target_index])
    record["pv_outcome"] = pv_verdict
    lines[target_index] = json.dumps(record)
    with open(jsonl_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _find_last_pending(lines):
    for index in range(len(lines) - 1, -1, -1):
        try:
            record = json.loads(lines[index])
        except (json.JSONDecodeError, ValueError):
            continue
        if record.get("pv_outcome") in (PENDING_PV, "", None):
            return index
    return None


def _mode_lookup(argv):
    if len(argv) < 10:
        return 0
    record = _build_record(argv)
    metrics_dir = argv[2]
    _append_jsonl(os.path.join(metrics_dir, "plan-cache.jsonl"), record)
    return 0


def _mode_pv(argv):
    if len(argv) < 5:
        return 0
    metrics_dir, _session, pv_verdict = argv[2], argv[3], argv[4]
    _writeback_pv(os.path.join(metrics_dir, "plan-cache.jsonl"), pv_verdict)
    return 0


def main(argv):
    if len(argv) < 2:
        return 0
    mode = argv[1]
    try:
        if mode == "lookup":
            return _mode_lookup(argv)
        if mode == "pv":
            return _mode_pv(argv)
    except (OSError, ValueError, TypeError):
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
