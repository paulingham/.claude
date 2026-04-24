#!/usr/bin/env bash
# Filters baseline + current case lists to the intersection of
# harness-ref-compatible cases (B5). Also excludes quarantined cases from
# regression math (A7).

_cf_dir="$(dirname "${BASH_SOURCE[0]}")"
# shellcheck source=compat-window.sh
source "$_cf_dir/compat-window.sh"

# filter_compatible_ids <run-sha> → stdout newline-separated case_ids to KEEP
# Reads EVAL_CASES_DIR + CLAUDE_HARNESS_REPO; if either unset, emits "*" (no filter).
filter_compatible_ids() {
  local run="$1"
  local cases="${EVAL_CASES_DIR:-}"
  local repo="${CLAUDE_HARNESS_REPO:-}"
  [ -n "$cases" ] && [ -n "$repo" ] && [ -n "$run" ] || { echo "*"; return; }
  _enumerate_compat "$cases" "$run" "$repo"
}

_enumerate_compat() {
  local cases="$1"; local run="$2"; local repo="$3"
  for meta in "$cases"/*/metadata.json; do
    [ -f "$meta" ] || continue
    _emit_if_ok "$meta" "$run" "$repo"
  done
}

_emit_if_ok() {
  local meta="$1"; local run="$2"; local repo="$3"
  local id; id="$(jq -r .case_id "$meta")"
  local tier; tier="$(jq -r '.flakiness_tier // "deterministic"' "$meta")"
  [ "$tier" = quarantined ] && return 0
  if case_compatible "$meta" "$run" "$repo"; then echo "$id"; fi
  return 0
}
