#!/usr/bin/env bash
# suite.json writer: run-level state (started/completed/interrupted).

# write_suite_state <out> <run-id> <suite> <model> <harness> <concurrency> <status>
write_suite_state() {
  local out="$1"; shift
  jq -n --arg rid "$1" --arg suite "$2" --arg model "$3" \
    --arg harness "$4" --argjson conc "$5" --arg status "$6" \
    --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    '{run_id:$rid,suite:$suite,model:$model,harness_ref:$harness,
      concurrency:$conc,status:$status,timestamp:$ts}' > "$out"
}
