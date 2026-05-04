#!/usr/bin/env bash
# Hook self-test — verifies registered PreToolUse hooks at SessionStart
# enforces: rules/core.md:Iron Laws
# protects: pipeline, all-skills
# Scope: registration + early-exit shape only. Fast-exit payloads, respects # self-test: skip.

source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "SessionStart"
trap 'log_hook_event $?' EXIT

SID="${CLAUDE_SESSION_ID:-local-$$}"
SID="${SID//[^a-zA-Z0-9_.-]/}"
METRICS="${HOME}/.claude/metrics/${SID}/hook-health.jsonl"
mkdir -p "$(dirname "$METRICS")"

CONFIG="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
HOOKS_DIR="$CONFIG/hooks"
FAST_PAYLOAD='{"tool_name":"Read","tool_input":{"file_path":"/dev/null"}}'
ANY_FAIL=0

for hook_path in "$HOOKS_DIR"/*.sh; do
  [[ -f "$hook_path" ]] || continue
  hook=$(basename "$hook_path")
  if [[ ! -x "$hook_path" ]]; then
    python3 -c "import json; print(json.dumps({'hook':'$hook','mode':'registration','outcome':'fail','reason':'not-executable'}))" >> "$METRICS"
    ANY_FAIL=1
    continue
  fi
  if ! bash -n "$hook_path" 2>/dev/null; then
    python3 -c "import json; print(json.dumps({'hook':'$hook','mode':'registration','outcome':'fail','reason':'syntax-error'}))" >> "$METRICS"
    ANY_FAIL=1
    continue
  fi
  if grep -q "^# self-test: skip" "$hook_path" 2>/dev/null; then
    python3 -c "import json; print(json.dumps({'hook':'$hook','mode':'registration','outcome':'ok'}))" >> "$METRICS"
  else
    RC=0
    echo "$FAST_PAYLOAD" | bash "$hook_path" >/dev/null 2>&1 || RC=$?
    if [[ $RC -ge 128 ]]; then
      python3 -c "import json; print(json.dumps({'hook':'$hook','mode':'invoked','outcome':'fail','reason':'crash-rc-$RC'}))" >> "$METRICS"
      ANY_FAIL=1
    else
      python3 -c "import json; print(json.dumps({'hook':'$hook','mode':'invoked','outcome':'ok','rc':$RC}))" >> "$METRICS"
    fi
  fi
done

[[ $ANY_FAIL -ne 0 ]] && echo "HOOK SELF-TEST: failures detected — check $METRICS" >&2
exit 0
