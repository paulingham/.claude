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
}

_render_report() {
  local arm_a="$1" arm_b="$2" preamble_b="$3" suite="$4" runs_dir="$5"
  python3 - "$arm_a" "$arm_b" "$preamble_b" "$suite" "$runs_dir" \
    "$SCORE_DIR/lib/ab_compare.py" <<'PYEOF'
import sys, json
from pathlib import Path

arm_a, arm_b, preamble_b, suite, runs_dir, lib_path = sys.argv[1:]
sys.path.insert(0, str(Path(lib_path).parent))
import ab_compare

def _load_scored(run_id):
    p = Path(runs_dir) / run_id / "cases.json"
    if not p.exists():
        return []
    data = json.loads(p.read_text())
    return data if isinstance(data, list) else data.get("cases", [])

scored_a = _load_scored(arm_a)
scored_b = _load_scored(arm_b)
r = ab_compare.compare_arms(arm_a_run_id=arm_a, arm_b_run_id=arm_b,
    scored_a=scored_a, scored_b=scored_b)
v = r["verdict"]
n_a, n_b = r.get("n_a", 0), r.get("n_b", 0)
saf_a = round(r.get("safety_a", 0.0) * 100, 1) if "safety_a" in r else 0.0
saf_b = round(r.get("safety_b", 0.0) * 100, 1) if "safety_b" in r else 0.0
dloc = r.get("loc_b", 0) - r.get("loc_a", 0) if "loc_a" in r else 0
usd_a = r.get("usd_a")
usd_b = r.get("usd_b")
dusd = round(usd_b - usd_a, 4) if (usd_a is not None and usd_b is not None) else None
proxy_a = "mutation score" if scored_a and "mutation_score" in scored_a[0] else "test-pass-rate"
proxy_b = "mutation score" if scored_b and "mutation_score" in scored_b[0] else "test-pass-rate"

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

main() {
  _parse_args "$@"
  local out_dir="${RUNS_DIR}/${ARM_A}-vs-${ARM_B}"
  mkdir -p "$out_dir"
  _render_report "$ARM_A" "$ARM_B" "$PREAMBLE_B" "$SUITE" "$RUNS_DIR" \
    > "$out_dir/ab-report.md"
  echo "[ab-compare] wrote $out_dir/ab-report.md"
}

main "$@"
