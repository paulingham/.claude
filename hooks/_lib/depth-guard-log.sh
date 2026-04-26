#!/usr/bin/env bash
# JSONL emit + log writer for depth-guard. Bash-3.2 clean.
# Usage: source this file, then call _dg_log_violation <depth> <max> <subagent_type>.

_dg_emit_record() {
  local ts="$1" sid="$2" tid="$3" depth="$4" max="$5" stype="$6"
  jq -nc --arg ts "$ts" --arg sid "$sid" --arg tid "$tid" --arg stype "$stype" \
    --argjson depth "$depth" --argjson max "$max" \
    '{record_type:"depth_violation",timestamp:$ts,session_id:$sid,task_id:$tid,depth:$depth,max_depth:$max,subagent_type:$stype,action:"prevented"}'
}

_dg_log_violation() {
  local depth="$1" max="$2" stype="$3" sid tid dir
  sid="${CLAUDE_SESSION_ID:-local-$$}"; sid="${sid//[^a-zA-Z0-9_.-]/}"
  tid="${CLAUDE_PIPELINE_TASK_ID:-}"; dir="$HOME/.claude/metrics/${sid:-local-$$}"
  mkdir -p "$dir" 2>/dev/null || return 0
  _dg_emit_record "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$sid" "$tid" "$depth" "$max" "$stype" \
    >> "$dir/depth-violations.jsonl" 2>/dev/null || true
}
