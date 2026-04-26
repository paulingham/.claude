#!/usr/bin/env bash
# Mode B — global scan of start files for over-cap subagents. Bash-3.2 clean.
# Source after resource-bounds.sh.

_rg_cap_for_class() {
  case "$1" in teammate) _max_runtime_teammate ;; *) _max_runtime_subagent ;; esac
}

_rg_log_violation() {
  local sid tid logf ts="$1" key="$2" disp="$3" class="$4" elapsed="$5" cap="$6"
  sid="${CLAUDE_SESSION_ID:-local-$$}"; sid="${sid//[^a-zA-Z0-9_.-]/}"
  tid="${CLAUDE_PIPELINE_TASK_ID:-}"
  logf="$HOME/.claude/metrics/${sid:-local-$$}/runtime-violations.jsonl"
  jq -nc --arg ts "$ts" --arg sid "$sid" --arg tid "$tid" --arg key "$key" \
    --arg disp "$disp" --arg class "$class" --argjson el "$elapsed" --argjson cap "$cap" \
    '{record_type:"runtime_violation",timestamp:$ts,session_id:$sid,task_id:$tid,agent_key:$key,display_name:$disp,class:$class,elapsed_seconds:$el,cap_seconds:$cap,action:"shutdown_signaled"}' \
    >> "$logf" 2>/dev/null || true
}

_rg_emit_block() {
  local disp="$1" class="$2" elapsed="$3" cap="$4"
  if [ "$class" = "teammate" ]; then
    printf 'BLOCKED: teammate runtime cap exceeded (shutdown_request).\n  agent: %s  class: teammate  elapsed: %ss  cap: %ss\nThe orchestrator should issue:\n  SendMessage({type:"shutdown_request", name:"%s"})\nSee rules/agent-protocol.md > Resource Bounds.\n' "$disp" "$elapsed" "$cap" "$disp" >&2
  else
    printf 'BLOCKED: subagent runtime cap exceeded.\n  agent: %s  class: subagent  elapsed: %ss  cap: %ss\nNext tool call blocked; orchestrator should re-dispatch per rules/operational-protocol.md.\nSee rules/agent-protocol.md > Resource Bounds.\n' "$disp" "$elapsed" "$cap" >&2
  fi
}

_rg_check_one() {
  local f="$1" now="$2" ts class disp elapsed cap key
  IFS=: read -r ts class disp < "$f" || return 0
  case "$ts" in ''|*[!0-9]*) return 0 ;; esac
  elapsed=$((now - ts)); cap=$(_rg_cap_for_class "$class")
  [ "$elapsed" -le "$cap" ] && return 0
  key="$(basename "$f" .start)"
  _rg_emit_block "$disp" "$class" "$elapsed" "$cap"
  _rg_log_violation "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$key" "$disp" "$class" "$elapsed" "$cap"
  return 1
}

_rg_scan_dir() {
  local dir="$1" now found=0
  [ -d "$dir" ] || return 0
  now=$(date +%s)
  for f in "$dir"/*.start; do
    [ -e "$f" ] || continue
    _rg_check_one "$f" "$now" || found=1
  done
  return "$found"
}
