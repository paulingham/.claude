#!/usr/bin/env bash
# /internal-eval score ab-compare — A/B diff-economy + safety-retention advisory report.
# Calls lib/ab_compare.py compare_arms(), renders ab-report.md. Advisory only — never gates.
set -eu
SCORE_DIR="$(cd "$(dirname "$0")" && pwd)"

_parse_args() {
  ARM_A=""; ARM_B=""; PREAMBLE_B="(none)"; SUITE="default"
  RUNS_DIR="${EVAL_RUNS_DIR:-$PWD/eval/runs}"
  while [ $# -gt 0 ]; do
    case "$1" in
      --arm-a)      ARM_A="$2";      shift 2 ;;
      --arm-b)      ARM_B="$2";      shift 2 ;;
      --preamble-b) PREAMBLE_B="$2"; shift 2 ;;
      --suite)      SUITE="$2";      shift 2 ;;
      *) echo "[ab-compare] unknown flag: $1" >&2; exit 2 ;;
    esac
  done
  [ -n "$ARM_A" ] || { echo "[ab-compare] --arm-a required" >&2; exit 2; }
  [ -n "$ARM_B" ] || { echo "[ab-compare] --arm-b required" >&2; exit 2; }
  case "$ARM_A" in */*|.*) echo "[ab-compare] invalid --arm-a: $ARM_A" >&2; exit 2 ;; esac
  case "$ARM_B" in */*|.*) echo "[ab-compare] invalid --arm-b: $ARM_B" >&2; exit 2 ;; esac
}

_render_report() {
  local arm_a="$1" arm_b="$2" preamble_b="$3" suite="$4" runs_dir="$5" costs_path="$6"
  python3 - "$arm_a" "$arm_b" "$preamble_b" "$suite" "$runs_dir" \
    "$SCORE_DIR/lib/ab_compare.py" "$costs_path" <<'PYEOF'
import sys, json
from pathlib import Path

arm_a, arm_b, preamble_b, suite, runs_dir, lib_path, costs_path = sys.argv[1:]
sys.path.insert(0, str(Path(lib_path).parent))
sys.path.insert(0, str(Path(lib_path).parent.parent.parent.parent.parent / "hooks" / "_lib"))
import ab_compare
from cost_estimator import estimate_cost_usd_for_run, USD_UNAVAILABLE_SENTINEL

USD_UNAVAIL_DISPLAY = "USD unavailable (no tagged records)"

def _load_scored(run_id):
    p = Path(runs_dir) / run_id / "cases.json"
    if not p.exists():
        return []
    data = json.loads(p.read_text())
    return data if isinstance(data, list) else data.get("cases", [])

def _usd_raw(run_id):
    result = estimate_cost_usd_for_run(run_id, costs_path)
    return None if result is USD_UNAVAILABLE_SENTINEL else result

def _per_arm_mutation(scored):
    if not scored:
        return None
    vals = [c["mutation_score"] for c in scored if "mutation_score" in c]
    return (sum(vals) / len(vals)) if vals else None

scored_a = _load_scored(arm_a)
scored_b = _load_scored(arm_b)
mut_a = _per_arm_mutation(scored_a)
mut_b = _per_arm_mutation(scored_b)
usd_a_raw = _usd_raw(arm_a)
usd_b_raw = _usd_raw(arm_b)

r = ab_compare.compare_arms(arm_a_run_id=arm_a, arm_b_run_id=arm_b,
    scored_a=scored_a, scored_b=scored_b,
    usd_a=usd_a_raw, usd_b=usd_b_raw,
    mutation_score_a=mut_a, mutation_score_b=mut_b)
v = r["verdict"]
n_a, n_b = r.get("n_a", 0), r.get("n_b", 0)
saf_a = round(r.get("safety_a", 0.0) * 100, 1) if "safety_a" in r else 0.0
saf_b = round(r.get("safety_b", 0.0) * 100, 1) if "safety_b" in r else 0.0
dloc = r.get("loc_b", 0) - r.get("loc_a", 0) if "loc_a" in r else 0
usd_a = r.get("usd_a")
usd_b = r.get("usd_b")
dusd = round(usd_b - usd_a, 4) if (usd_a is not None and usd_b is not None) else None

def _tok_sum(scored):
    return sum(c.get("input_tokens", 0) + c.get("output_tokens", 0) for c in scored)

tok_a = _tok_sum(scored_a)
tok_b = _tok_sum(scored_b)

proxy_a = "mutation score" if mut_a is not None else "test-pass-rate"
proxy_b = "mutation score" if mut_b is not None else "test-pass-rate"

usd_a_cell = f"${usd_a:.4f}" if usd_a is not None else USD_UNAVAIL_DISPLAY
usd_b_cell = f"${usd_b:.4f}" if usd_b is not None else USD_UNAVAIL_DISPLAY
usd_d_cell = f"${dusd:.4f}" if dusd is not None else USD_UNAVAIL_DISPLAY

lines = [
    "# A/B Diff-Economy Report", "",
    f"| | Arm A | Arm B |",
    f"|---|---|---|",
    f"| Run ID | `{arm_a}` | `{arm_b}` |",
    f"| Preamble | (none) | {preamble_b} |",
    f"| Suite | {suite} | {suite} |",
    f"| Cases scored | {n_a} | {n_b} |",
    f"| Safety proxy | {proxy_a} | {proxy_b} |",
    "",
    "## Metrics",
    "",
    "| Metric | Arm A | Arm B | Δ |",
    "|---|---|---|---|",
    f"| LOC (net added) | {r.get('loc_a', 'n/a')} | {r.get('loc_b', 'n/a')} | {dloc} |",
    f"| Tokens | {tok_a} | {tok_b} | {tok_b - tok_a} |",
    f"| USD | {usd_a_cell} | {usd_b_cell} | {usd_d_cell} |",
    f"| Safety % | {saf_a}% | {saf_b}% | {round(saf_b - saf_a, 1)} |",
    "",
    "## Verdict", "",
]

if v == "EVAL_IMPROVEMENT_CONFIRMED":
    usd_str = f"${abs(dusd):.4f}" if dusd is not None else "N/A"
    lines.append(f"EVAL_IMPROVEMENT_CONFIRMED — arm B cut diff-economy (LOC −{abs(dloc)}, USD −{usd_str}) with safety held ({saf_b}% ≥ {saf_a}%). Advisory only; gates nothing.")
elif v == "EVAL_REGRESSION_DETECTED":
    lines.append(f"EVAL_REGRESSION_DETECTED — arm B safety dropped ({saf_b}% < {saf_a}%); diff-economy wins are disregarded by design (Iron Law 1). Advisory only; gates nothing.")
elif v == "EVAL_NEUTRAL":
    usd_str = f"${dusd:.4f}" if dusd is not None else "N/A"
    lines.append(f"EVAL_NEUTRAL — safety held but no diff-economy change beyond noise (LOC Δ {dloc}, USD Δ {usd_str}). Advisory only; gates nothing.")
else:
    lines.append(f"INSUFFICIENT — one or both arms scored 0 cases (A={n_a}, B={n_b}); no comparison computed. Fail-closed refusal, NOT a 100% pass.")

print("\n".join(lines))
PYEOF
}

_resolve_costs_path() {
  local data_root="${CLAUDE_PLUGIN_DATA:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}"
  echo "${EVAL_COSTS_JSONL:-$data_root/metrics/costs.jsonl}"
}

main() {
  _parse_args "$@"
  local out_dir="${RUNS_DIR}/${ARM_A}-vs-${ARM_B}"
  mkdir -p "$out_dir"
  local costs_path
  costs_path="$(_resolve_costs_path)"
  _render_report "$ARM_A" "$ARM_B" "$PREAMBLE_B" "$SUITE" "$RUNS_DIR" "$costs_path" \
    > "$out_dir/ab-report.md"
  echo "[ab-compare] wrote $out_dir/ab-report.md"
}

main "$@"
