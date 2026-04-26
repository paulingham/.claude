#!/usr/bin/env bash
# await-pattern-emit.sh — JSONL emission for await-pattern.
# Public functions: _aw_emit_match, _aw_emit_timeout.
# Schema: record_type ∈ {await_match,await_timeout}; common fields:
#   timestamp, session_id, task_id, log_path, regex,
#   timeout_seconds:int, elapsed_seconds:int.
# await_match adds: matched_line (≤512 chars).
# await_timeout adds: lines_scanned:int.

_aw_emit_common() {
  jq -nc --arg rt "$1" --arg ts "$2" --arg sid "$3" --arg tid "$4" \
    --arg lp "$5" --arg rx "$6" --argjson to "$7" --argjson el "$8" \
    '{record_type:$rt,timestamp:$ts,session_id:$sid,task_id:$tid,log_path:$lp,regex:$rx,timeout_seconds:$to,elapsed_seconds:$el}'
}

_aw_emit_match() {
  local out="$1" ts="$2" sid="$3" tid="$4" lp="$5" rx="$6" to="$7" el="$8" line="$9"
  _aw_emit_common await_match "$ts" "$sid" "$tid" "$lp" "$rx" "$to" "$el" \
    | jq -c --arg line "${line:0:512}" '. + {matched_line:$line}' >> "$out"
}

_aw_emit_timeout() {
  local out="$1" ts="$2" sid="$3" tid="$4" lp="$5" rx="$6" to="$7" el="$8" scanned="$9"
  _aw_emit_common await_timeout "$ts" "$sid" "$tid" "$lp" "$rx" "$to" "$el" \
    | jq -c --argjson n "$scanned" '. + {lines_scanned:$n}' >> "$out"
}
