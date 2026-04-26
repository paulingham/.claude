#!/usr/bin/env bash
# Post-run mutation: rewrites stub-produced failed_build statuses to
# failed_diff (matches oracle-rejection semantics) and re-aggregates so
# aggregate.json reflects the rewritten per-case statuses.

_mut_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_MUT_ROOT="$(cd "$_mut_dir/../.." && pwd)"

rewrite_failed_as_diff() {
  local run_dir="$1"
  for f in "$run_dir"/cases/*/result.json; do
    [ -f "$f" ] || continue
    _rewrite_one "$f"
  done
}

_rewrite_one() {
  local f="$1"
  local status; status="$(jq -r .status "$f")"
  [ "$status" = "failed_build" ] || return 0
  local tmp; tmp="$(mktemp)"
  jq '.status = "failed_diff"' "$f" > "$tmp" && mv "$tmp" "$f"
}

reaggregate() {
  local run_dir="$1"; local run_id="$2"
  # shellcheck disable=SC1091
  source "$_MUT_ROOT/run/lib/suite-aggregate.sh"
  aggregate_run "$run_dir" "$run_id" default opus live
}
