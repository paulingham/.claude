#!/usr/bin/env bash
# spec-blind-read-guard PreToolUse hook (Read|Grep|Glob).
#
# Blocks the spec-blind-validator from reading paths outside the public-surface
# allowlist (hooks/_lib/spec-blind-allow-paths.txt). For every other subagent,
# fast-exits 0 — AC17 budgets < 25ms median for this no-op path.
#
# IF SPEC-BLIND READS ARE LEAKING: check the .subagent_type top-level JSON field
# is present in stdin (verified at hooks/planning-agent-edit-scope.sh:24,
# hooks/cost-feed.sh:33).
# IF READS ARE OVER-BLOCKING: check the path matrix in
# tests/shell/test_spec_blind_read_guard.bats — and the pattern list in
# hooks/_lib/spec-blind-allow-paths.txt.
#
# enforces: rules/_detail/pipeline-protocol.md (Final Gate § In-Cycle Fix Rule)
# protects: spec-blind-validate

set -uo pipefail

# AC17 fast-exit: read raw stdin once, fast-substring-test for the subagent
# token BEFORE invoking jq. False positive here is fast non-block — the JSON
# parse below confirms exact match before any deny decision.
INPUT=$(cat)
if ! printf '%s' "$INPUT" | grep -F -q "spec-blind-validator"; then
  exit 0
fi

# Lazy-load logging only when we know we'll potentially block.
# shellcheck source=/dev/null
source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "PreToolUse:Read|Grep|Glob"
trap 'log_hook_event $?' EXIT

TOOL_NAME=$(printf '%s' "$INPUT" | jq -r '.tool_name // empty')
SUBAGENT_TYPE=$(printf '%s' "$INPUT" | jq -r '.subagent_type // empty')
FILE_PATH=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // .tool_input.pattern // empty')
SESSION_RAW=$(printf '%s' "$INPUT" | jq -r '.session_id // empty')
SESSION=$(printf '%s' "$SESSION_RAW" | tr -dc 'A-Za-z0-9_-' | head -c 64)
[[ -z "$SESSION" ]] && SESSION="unknown"

# Exact-match comparison — substring "spec-blind-validator-v2" would not match here.
[[ "$SUBAGENT_TYPE" != "spec-blind-validator" ]] && exit 0
case "$TOOL_NAME" in
  Read|Grep|Glob) ;;
  *) exit 0 ;;
esac

# No path → nothing to check (e.g. Glob with default cwd) — let it through.
[[ -z "$FILE_PATH" ]] && exit 0

# Resolve relative paths against pwd so absolute-prefix patterns can match.
case "$FILE_PATH" in
  /*) ABS_PATH="$FILE_PATH" ;;
  *)  ABS_PATH="$(pwd)/$FILE_PATH" ;;
esac

# shellcheck source=/dev/null
source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/spec-blind-allow-paths.sh"

if is_path_allowed_for_spec_blind "$ABS_PATH"; then
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
  --arg guard "read-guard" \
  '{ts:$ts, record_type:"spec_blind_blocked", subagent_type:$subagent, tool:$tool, attempted_path:$path, session_id:$session, guard:$guard, action:"blocked"}' \
  >> "$LOG_FILE" 2>/dev/null

echo "BLOCKED: spec-blind-validator may not read $FILE_PATH. See skills/spec-blind-validate/SKILL.md § Public API Surface." >&2
exit 2
