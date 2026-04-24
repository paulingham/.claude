#!/usr/bin/env bash
# Flakiness-tier retry. Invokes the scoring callback 1-2 times per tier and
# emits `attempts=N` on stdout so result.json can record the attempt count.

# score_with_retry <tier> <callback> [args...]
#   deterministic, quarantined → 1 attempt
#   retriable-2x               → up to 2 attempts, stops on first success
# Returns the last callback rc. Always echoes "attempts=N".
score_with_retry() {
  local tier="$1"; shift
  local budget; budget="$(_tier_budget "$tier")"
  _attempt_loop "$budget" "$@"
}

_tier_budget() {
  case "$1" in retriable-2x) echo 2 ;; *) echo 1 ;; esac
}

_attempt_loop() {
  local budget="$1"; shift
  local n=0 rc=1
  while [ "$n" -lt "$budget" ]; do
    n=$((n+1)); "$@"; rc=$?
    [ "$rc" -eq 0 ] && break
  done
  echo "attempts=$n"; return "$rc"
}
