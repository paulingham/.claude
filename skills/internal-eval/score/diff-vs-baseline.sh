#!/usr/bin/env bash
# /internal-eval score diff-vs-baseline — computes 4-quadrant regression diff
# and writes eval/runs/{run-id}/regression.json + regression.md.
set -eu
SCORE_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=lib/baseline-parse.sh
source "$SCORE_DIR/lib/baseline-parse.sh"
# shellcheck source=lib/regression-args.sh
source "$SCORE_DIR/lib/regression-args.sh"
# shellcheck source=lib/regression-compute.sh
source "$SCORE_DIR/lib/regression-compute.sh"
# shellcheck source=lib/regression-md.sh
source "$SCORE_DIR/lib/regression-md.sh"

main() {
  parse_regression_args "$@"
  local agg="$RUNS_DIR/$RUN_ID/aggregate.json"
  [ -f "$agg" ] || { echo "[diff-vs-baseline] missing: $agg" >&2; exit 2; }
  [ -f "$BASELINE" ] || { echo "[diff-vs-baseline] missing baseline: $BASELINE" >&2; exit 2; }
  _emit_reports "$agg"
}

_emit_reports() {
  local agg="$1"; local out="$RUNS_DIR/$RUN_ID/regression.json"
  compute_regression_json "$BASELINE" "$agg" > "$out"
  render_regression_md "$out" > "$RUNS_DIR/$RUN_ID/regression.md"
  echo "$(jq -r .verdict "$out")"
}

main "$@"
