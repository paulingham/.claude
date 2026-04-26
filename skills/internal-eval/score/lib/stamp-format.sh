#!/usr/bin/env bash
# Story 9 — format helpers for the PR-body eval-baseline stamp.

_fm_field() {
  sed -n "s/^$2: *\(.*\)$/\1/p" "$1" | head -1
}

_fm_or_default() {
  local val; val="$(_fm_field "$1" "$2")"
  [ -n "$val" ] && echo "$val" || echo "$3"
}

emit_stamp_stub() {
  echo "## Eval Baseline"
  echo
  echo "_not yet captured — run \`/internal-eval run\` to establish baseline._"
}

emit_stamp_body() {
  local file="$1"; local now="$2"; local rel_path="$3"
  local pr; pr="$(_fm_or_default "$file" pass_rate ?)"
  local p; p="$(_fm_or_default "$file" passed ?)"
  local tot; tot="$(_fm_or_default "$file" total_cases ?)"
  _emit_header "$file" "$pr" "$p" "$tot" "$rel_path" "$now"
}

_emit_header() {
  echo "## Eval Baseline"; echo
  _emit_bullets "$@"; echo
  echo "_Measured on this baseline, not SWE-bench. See \`~/.claude/skills/internal-eval/\` for methodology._"
}

_emit_bullets() {
  echo "- **Pass rate**: $2 ($3/$4 cases passed)"
  echo "- **Harness ref**: \`$(_fm_or_default "$1" harness_ref unknown)\`"
  echo "- **Baseline date**: $(_fm_or_default "$1" baseline_date unknown)"
  _emit_bullets_tail "$1" "$5" "$6"
}

_emit_bullets_tail() {
  echo "- **Model**: $(_fm_or_default "$1" model unknown)"
  echo "- **Baseline file**: [$2]($2)"
  echo "- **Stamped at**: $3"
}
