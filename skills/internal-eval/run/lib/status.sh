#!/usr/bin/env bash
# Per-case status enum + result.json writer for /internal-eval run-case.
# Keep functions <= 5 lines, files <= 50 lines (manual shell shape).

# Allowed per-case statuses. See skills/internal-eval/run/SKILL.md § status enum.
RUN_CASE_STATUSES="passed failed_diff failed_build failed_timeout failed_infra dry_run_ok"

is_valid_status() {
  local candidate="$1"
  case " $RUN_CASE_STATUSES " in *" $candidate "*) return 0 ;; esac
  return 1
}

# Bash 3 compatible: read k=v pairs via _kv_get. No associative arrays.
_kv_get() {
  local key="$1"; shift
  for pair in "$@"; do case "$pair" in "$key"=*) echo "${pair#*=}"; return ;; esac; done
}

# write_result_json <path> k=v ... (keys: case run status duration cost rounds
# rework harness model flakiness scoring ts inner reason).
write_result_json() {
  local out="$1"; shift
  jq -n \
    --arg case_id "$(_kv_get case "$@")" --arg run_id "$(_kv_get run "$@")" \
    --arg status "$(_kv_get status "$@")" --argjson dur "$(_kv_get duration "$@")" \
    --argjson cost "$(_kv_get cost "$@")" --argjson rounds "$(_kv_get rounds "$@")" \
    --argjson rework "$(_kv_get rework "$@")" --arg harness "$(_kv_get harness "$@")" \
    --arg model "$(_kv_get model "$@")" --arg flak "$(_kv_get flakiness "$@")" \
    --arg scoring "$(_kv_get scoring "$@")" --arg ts "$(_kv_get ts "$@")" \
    --arg inner "$(_kv_get inner "$@")" --arg reason "$(_kv_get reason "$@")" \
    '{case_id:$case_id,run_id:$run_id,status:$status,duration_sec:$dur,
      cost_usd:$cost,review_rounds:$rounds,rework:$rework,harness_ref:$harness,
      model:$model,flakiness_tier:$flak,scoring_mode:$scoring,timestamp:$ts,
      inner_pipeline_state:$inner,failure_reason:$reason}' > "$out"
}
