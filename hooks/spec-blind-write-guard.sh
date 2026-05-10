#!/usr/bin/env bash
# spec-blind-write-guard PreToolUse hook (Write|Edit).
#
# Allows the spec-blind-validator to Write/Edit ONLY under test directories
# (tests/, test/, spec/, __tests__/). Read-allowlist files (interface.ts,
# package.json, README.md, etc.) are READ-ONLY for this validator — the
# write-allowlist is strictly tighter than the read-allowlist.
#
# For every other subagent, fast-exits 0. AC17-style early-exit branch
# (grep -F over raw stdin BEFORE jq) ensures no overhead on the no-op path.
#
# IF SPEC-BLIND WRITES ARE LEAKING: check the .subagent_type top-level JSON
# field is present in stdin.
# IF WRITES ARE OVER-BLOCKING legitimate test paths: check the directory
# globs in hooks/_lib/spec-blind-allow-paths.sh::is_path_allowed_for_spec_blind_write.
#
# enforces: rules/_detail/pipeline-protocol.md (Final Gate § In-Cycle Fix Rule)
# protects: spec-blind-validate

set -uo pipefail

INPUT=$(cat)
if ! printf '%s' "$INPUT" | grep -F -q "spec-blind-validator"; then
  exit 0
fi

# shellcheck source=/dev/null
source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "PreToolUse:Write|Edit"
trap 'log_hook_event $?' EXIT

TOOL_NAME=$(printf '%s' "$INPUT" | jq -r '.tool_name // empty')
SUBAGENT_TYPE=$(printf '%s' "$INPUT" | jq -r '.subagent_type // empty')
FILE_PATH=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty')
SESSION_RAW=$(printf '%s' "$INPUT" | jq -r '.session_id // empty')
SESSION=$(printf '%s' "$SESSION_RAW" | tr -dc 'A-Za-z0-9_-' | head -c 64)
[[ -z "$SESSION" ]] && SESSION="unknown"

[[ "$SUBAGENT_TYPE" != "spec-blind-validator" ]] && exit 0
case "$TOOL_NAME" in
  Write|Edit) ;;
  *) exit 0 ;;
esac

[[ -z "$FILE_PATH" ]] && exit 0

case "$FILE_PATH" in
  /*) ABS_PATH="$FILE_PATH" ;;
  *)  ABS_PATH="$(pwd)/$FILE_PATH" ;;
esac

# shellcheck source=/dev/null
source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/spec-blind-allow-paths.sh"

if is_path_allowed_for_spec_blind_write "$ABS_PATH"; then
  exit 0
fi

LOG_DIR="${HOME:-/tmp}/.claude/metrics/$SESSION"
mkdir -p "$LOG_DIR" 2>/dev/null || exit 2
LOG_FILE="$LOG_DIR/spec-blind-violations.jsonl"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
jq -nc \
  --arg ts "$TS" \
  --arg subagent "spec-blind-validator" \
  --arg tool "$TOOL_NAME" \
  --arg path "$FILE_PATH" \
  --arg session "$SESSION" \
  --arg guard "write-guard" \
  '{ts:$ts, record_type:"spec_blind_blocked", subagent_type:$subagent, tool:$tool, attempted_path:$path, session_id:$session, guard:$guard, action:"blocked"}' \
  >> "$LOG_FILE" 2>/dev/null

echo "BLOCKED: spec-blind-validator may not write $FILE_PATH. Allowed write targets: tests/**, test/**, spec/**, __tests__/**." >&2
exit 2
