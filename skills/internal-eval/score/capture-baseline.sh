#!/usr/bin/env bash
# /internal-eval score capture-baseline — writes eval/baselines/{date}-{model}.md
# from the named run's aggregate.json and updates the latest-{model}.md symlink.
set -eu
SCORE_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=lib/baseline-write.sh
source "$SCORE_DIR/lib/baseline-write.sh"
# shellcheck source=lib/baseline-args.sh
source "$SCORE_DIR/lib/baseline-args.sh"

main() {
  parse_baseline_args "$@"
  local agg="${EVAL_RUNS_DIR:-$PWD/eval/runs}/$RUN_ID/aggregate.json"
  [ -f "$agg" ] || { echo "[capture-baseline] missing: $agg" >&2; exit 2; }
  _capture "$agg"
}

_capture() {
  local agg="$1"
  local model; model="$(jq -r .model "$agg")"
  local date; date="$(jq -r '.completed_at | .[0:10]' "$agg")"
  local out_dir="${EVAL_BASELINES_DIR:-$PWD/eval/baselines}"
  mkdir -p "$out_dir"
  local file="$date-$model.md"
  write_baseline "$out_dir/$file" "$agg" "$date"
  _relink "$out_dir" "$model" "$file"
}

_relink() {
  local dir="$1"; local model="$2"; local target="$3"
  local link="$dir/latest-$model.md"
  rm -f "$link"; (cd "$dir" && ln -s "$target" "latest-$model.md")
}

main "$@"
