#!/usr/bin/env bash
# Block message + JSONL log emission for runtime-guard. Bash-3.2 clean.
# Sourced by runtime-guard-check.sh.

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/harness-paths.sh"
_rg_emit_teammate_block() {
  printf 'BLOCKED: teammate runtime cap exceeded (shutdown_request).\n  agent: %s  class: teammate  elapsed: %ss  cap: %ss\nThe orchestrator should issue:\n  SendMessage({type:"shutdown_request", name:"%s"})\nSee protocols/agent-protocol.md > Resource Bounds.\n' "$1" "$2" "$3" "$1" >&2
}

_rg_emit_subagent_block() {
  printf 'BLOCKED: subagent runtime cap exceeded.\n  agent: %s  class: subagent  elapsed: %ss  cap: %ss\nNext tool call blocked; orchestrator should re-dispatch per protocols/operational-protocol.md.\nSee protocols/agent-protocol.md > Resource Bounds.\n' "$1" "$2" "$3" >&2
}

_rg_emit_block() {
  case "$2" in
    teammate) _rg_emit_teammate_block "$1" "$3" "$4" ;;
    *)        _rg_emit_subagent_block "$1" "$3" "$4" ;;
  esac
}

_rg_make_log_record() {
  jq -nc --arg ts "$1" --arg sid "$2" --arg tid "$3" --arg key "$4" \
    --arg disp "$5" --arg class "$6" --argjson el "$7" --argjson cap "$8" \
    '{record_type:"runtime_violation",timestamp:$ts,session_id:$sid,task_id:$tid,agent_key:$key,display_name:$disp,class:$class,elapsed_seconds:$el,cap_seconds:$cap,action:"shutdown_signaled"}'
}

_rg_log_violation() {
  local sid tid logf
  sid="${CLAUDE_SESSION_ID:-local-$$}"; sid="${sid//[^a-zA-Z0-9_.-]/}"
  tid="${CLAUDE_PIPELINE_TASK_ID:-}"
  logf="$HARNESS_DATA/metrics/${sid:-local-$$}/runtime-violations.jsonl"
  _rg_make_log_record "$1" "$sid" "$tid" "$2" "$3" "$4" "$5" "$6" >> "$logf" 2>/dev/null || true
}
