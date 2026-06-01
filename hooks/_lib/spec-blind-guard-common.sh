#!/usr/bin/env bash
# Common parsing + violation-logging helpers shared by the three spec-blind
# guards (read / write / bash). Extracted (CR-MED-1) to remove ~25 LOC of
# duplicated mechanics per guard.
#
# Public functions:
#   _spec_blind_parse_input  — sets TOOL_NAME / SUBAGENT_TYPE / SESSION /
#                              FILE_PATH / COMMAND on the global env from the
#                              jq-parsed stdin INPUT (must be set by caller).
#                              SUBAGENT_TYPE falls back to CLAUDE_SUBAGENT_TYPE
#                              env var when the JSON field is empty
#                              (SEC-MED-2 fail-open mitigation, mirrors
#                              hooks/cost-feed.sh:33).
#   _spec_blind_redact <str> — applies the canonical secret-redaction patterns
#                              (Bearer / token / secret / password / api_key /
#                              aws_secret) and prints the redacted form on
#                              stdout (SEC-MED-1).
#   _spec_blind_log_violation <guard> <tool> <attempted-target> [<offender>]
#                            — appends one JSONL violation record to
#                              $HARNESS_DATA/metrics/$SESSION/spec-blind-violations.jsonl.
#                              Caller passes the target (path or full command)
#                              and an optional offender word for bash-guard.
#                              Secrets in the target are redacted before
#                              writing (SEC-MED-1).
#
# enforces: protocols/pipeline-protocol.md (Final Gate § In-Cycle Fix Rule)
# protects: spec-blind-validate

# Parse the standard PreToolUse JSON envelope into shell vars. Caller must
# have already read stdin into $INPUT. SUBAGENT_TYPE fallback chain:
#   1. .subagent_type top-level JSON field
#   2. CLAUDE_SUBAGENT_TYPE env var (canonical, set by orchestrator)
# If both are empty, SUBAGENT_TYPE stays empty and the guard's fast-exit
# branch decides what to do (default-deny vs default-allow per guard).
# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/harness-paths.sh"
_spec_blind_parse_input() {
  TOOL_NAME=$(printf '%s' "$INPUT" | jq -r '.tool_name // empty')
  SUBAGENT_TYPE=$(printf '%s' "$INPUT" | jq -r '.subagent_type // empty')
  [[ -z "$SUBAGENT_TYPE" ]] && SUBAGENT_TYPE="${CLAUDE_SUBAGENT_TYPE:-}"
  FILE_PATH=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // .tool_input.pattern // empty')
  COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')
  local sid_raw
  sid_raw=$(printf '%s' "$INPUT" | jq -r '.session_id // empty')
  SESSION=$(printf '%s' "$sid_raw" | tr -dc 'A-Za-z0-9_-' | head -c 64)
  [[ -z "$SESSION" ]] && SESSION="unknown"
}

# Redact common secret shapes from a string. The pattern set is the minimum
# called out in SEC-MED-1: Bearer/token/secret/password/api[_-]?key/aws[_-]?secret
# tokens followed by a non-space run are replaced with ***REDACTED***.
# Case-insensitive. Non-greedy enough to leave structural punctuation intact.
_spec_blind_redact() {
  printf '%s' "$1" | sed -E '
    s/([Bb][Ee][Aa][Rr][Ee][Rr])[[:space:]]+[^[:space:]"'\'']+/\1 ***REDACTED***/g
    s/([Tt][Oo][Kk][Ee][Nn])[[:space:]]*[:=][[:space:]]*[^[:space:]"'\'']+/\1=***REDACTED***/g
    s/([Ss][Ee][Cc][Rr][Ee][Tt])[[:space:]]*[:=][[:space:]]*[^[:space:]"'\'']+/\1=***REDACTED***/g
    s/([Pp][Aa][Ss][Ss][Ww][Oo][Rr][Dd])[[:space:]]*[:=][[:space:]]*[^[:space:]"'\'']+/\1=***REDACTED***/g
    s/([Aa][Pp][Ii][_-]?[Kk][Ee][Yy])[[:space:]]*[:=][[:space:]]*[^[:space:]"'\'']+/\1=***REDACTED***/g
    s/([Aa][Ww][Ss][_-]?[Ss][Ee][Cc][Rr][Ee][Tt])[[:space:]]*[:=][[:space:]]*[^[:space:]"'\'']+/\1=***REDACTED***/g
  '
}

# Append one JSONL violation record. Bash-guard passes the full command as
# `target` plus an `offender` word; read/write guards pass the file path as
# `target` and omit `offender`. The target string is redacted before writing.
_spec_blind_log_violation() {
  local guard="$1" tool="$2" target="$3" offender="${4:-}"
  local log_dir="$HARNESS_DATA/metrics/$SESSION"
  mkdir -p "$log_dir" 2>/dev/null || return 1
  local log_file="$log_dir/spec-blind-violations.jsonl"
  local ts
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  local redacted
  redacted="$(_spec_blind_redact "$target")"
  local target_field="attempted_path"
  [[ "$guard" == "bash-guard" ]] && target_field="attempted_command"
  if [[ -n "$offender" ]]; then
    jq -nc \
      --arg ts "$ts" \
      --arg subagent "spec-blind-validator" \
      --arg tool "$tool" \
      --arg target "$redacted" \
      --arg offender "$offender" \
      --arg session "$SESSION" \
      --arg guard "$guard" \
      --arg field "$target_field" \
      '{ts:$ts, record_type:"spec_blind_blocked", subagent_type:$subagent, tool:$tool, ($field):$target, offender:$offender, session_id:$session, guard:$guard, action:"blocked"}' \
      >> "$log_file" 2>/dev/null
  else
    jq -nc \
      --arg ts "$ts" \
      --arg subagent "spec-blind-validator" \
      --arg tool "$tool" \
      --arg target "$redacted" \
      --arg session "$SESSION" \
      --arg guard "$guard" \
      --arg field "$target_field" \
      '{ts:$ts, record_type:"spec_blind_blocked", subagent_type:$subagent, tool:$tool, ($field):$target, session_id:$session, guard:$guard, action:"blocked"}' \
      >> "$log_file" 2>/dev/null
  fi
}
