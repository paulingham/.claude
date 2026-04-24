#!/usr/bin/env bash
# Bash-3.2-compatible job pool. Spawns N cases with max <concurrency> in flight.
# Uses jobs -r -p (running-only PIDs) for the cap; no `wait -n` (bash 4.3+).

# run_pool <concurrency> <launcher_fn> <case_id...>
run_pool() {
  local max="$1"; local launcher="$2"; shift 2
  for c in "$@"; do _pool_throttle "$max"; "$launcher" "$c" & done
  wait
}

_pool_throttle() {
  local max="$1"
  while [ "$(_running_jobs)" -ge "$max" ]; do sleep 0.05; done
}

_running_jobs() { jobs -r -p 2>/dev/null | wc -l | tr -d ' '; }
