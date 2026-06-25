#!/usr/bin/env bash
# Projects per-case result.json + costs.jsonl into cases.json for ab-compare.sh.
# Output shape: [{case, pass, loc_added, loc_removed, input_tokens, output_tokens}, ...]
#
# Usage: write_cases_json <run-dir> <run-id>

write_cases_json() {
  local run_dir="$1" run_id="$2"
  local costs_path
  costs_path="$(_cases_costs_path)"
  python3 - "$run_dir" "$run_id" "$costs_path" <<'PYEOF'
import sys, json
from pathlib import Path

run_dir, run_id, costs_path = Path(sys.argv[1]), sys.argv[2], sys.argv[3]

def _read_costs(costs_path, run_id):
    by_case = {}
    try:
        with open(costs_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if r.get("eval_run_id") != run_id:
                    continue
                cid = r.get("eval_case_id", "")
                entry = by_case.setdefault(cid, {"input_tokens": 0, "output_tokens": 0})
                def _safe_int(v):
                    try:
                        return int(v or 0)
                    except (TypeError, ValueError):
                        return 0
                entry["input_tokens"] += _safe_int(r.get("input_tokens", 0))
                entry["output_tokens"] += _safe_int(r.get("output_tokens", 0))
    except FileNotFoundError:
        pass
    return by_case

def _read_loc(run_dir, case_id):
    # WHY: inner_state_dir is OPTIONAL today (no inner emits net-numstat yet).
    # Future wire: inner pipeline writes net-numstat to
    #   ${EVAL_RUNS_DIR}/${EVAL_RUN_ID}/inner/${EVAL_CASE_ID}/net-numstat
    # That path is derivable from already-exported env vars — no extra plumbing needed.
    p = run_dir / "inner" / case_id / "net-numstat"
    if not p.exists():
        return 0, 0
    text = p.read_text().strip()
    parts = text.split()
    if len(parts) < 2:
        return 0, 0
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return 0, 0

costs = _read_costs(costs_path, run_id)
cases_dir = run_dir / "cases"
records = []
for result_path in sorted(cases_dir.glob("*/result.json")):
    case_id = result_path.parent.name
    try:
        result = json.loads(result_path.read_text())
    except (json.JSONDecodeError, OSError):
        continue
    status = result.get("status", "")
    tok = costs.get(case_id, {"input_tokens": 0, "output_tokens": 0})
    loc_added, loc_removed = _read_loc(run_dir, case_id)
    records.append({
        "case": case_id,
        "pass": status == "passed",
        "loc_added": loc_added,
        "loc_removed": loc_removed,
        "input_tokens": tok["input_tokens"],
        "output_tokens": tok["output_tokens"],
    })

(run_dir / "cases.json").write_text(json.dumps(records, indent=2))
PYEOF
}

_cases_costs_path() {
  local data_root="${CLAUDE_PLUGIN_DATA:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}"
  echo "${EVAL_COSTS_JSONL:-$data_root/metrics/costs.jsonl}"
}
