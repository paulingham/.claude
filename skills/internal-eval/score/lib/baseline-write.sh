#!/usr/bin/env bash
# Baseline writer: serialises an aggregate.json into a per-model baseline
# markdown file under eval/baselines/. Frontmatter is the machine-readable
# contract; the per-case table is for human review + regression diff input.

_bw_dir="$(dirname "${BASH_SOURCE[0]}")"

# write_baseline <out.md> <aggregate.json> <baseline-date>
write_baseline() {
  local out="$1"; local agg="$2"; local date="$3"
  { _emit_frontmatter "$agg" "$date"; _emit_case_table "$agg"; } > "$out"
}

_emit_frontmatter() {
  jq -r --arg d "$2" -f "$_bw_dir/baseline-frontmatter.jq" "$1"
}

_emit_case_table() {
  echo "## Per-Case Results"; echo; echo "| case_id | status |"; echo "|---|---|"
  jq -r '.case_results[] | "| \(.case_id) | \(.status) |"' "$1"
}
