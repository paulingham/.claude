#!/usr/bin/env bash
# Hook self-test — verifies registered PreToolUse hooks at SessionStart
# enforces: rules/core.md:Iron Laws
# protects: pipeline, all-skills
# self-test: skip
# Scope: registration + early-exit shape only. Fast-exit payloads, respects # self-test: skip.

source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/log.sh"
# Inline emitter — matches _lib/jsonl-emit.sh contract. Inlined because
# hook-self-test.sh runs at SessionStart before _lib/ is guaranteed loaded.
_jsonl_emit() {
  local out="$1"; shift
  python3 - "$@" >> "$out" <<'PY'
import json, sys, time
a = sys.argv[1:]
d = {a[i]: a[i+1] for i in range(0, len(a) - 1, 2)}
d["ts"] = int(time.time())
print(json.dumps(d))
PY
}
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
  [[ "$hook" == "hook-self-test.sh" ]] && continue
  if [[ ! -x "$hook_path" ]]; then
    _jsonl_emit "$METRICS" hook "$hook" mode registration outcome fail reason not-executable
    ANY_FAIL=1
    continue
  fi
  if ! bash -n "$hook_path" 2>/dev/null; then
    _jsonl_emit "$METRICS" hook "$hook" mode registration outcome fail reason syntax-error
    ANY_FAIL=1
    continue
  fi
  if grep -q "^# self-test: skip" "$hook_path" 2>/dev/null; then
    _jsonl_emit "$METRICS" hook "$hook" mode registration outcome ok
  else
    RC=0
    echo "$FAST_PAYLOAD" | bash "$hook_path" >/dev/null 2>&1 || RC=$?
    if [[ $RC -ge 128 ]]; then
      _jsonl_emit "$METRICS" hook "$hook" mode invoked outcome fail reason "crash-rc-$RC"
      ANY_FAIL=1
    else
      _jsonl_emit "$METRICS" hook "$hook" mode invoked outcome ok rc "$RC"
    fi
  fi
done

[[ $ANY_FAIL -ne 0 ]] && echo "HOOK SELF-TEST: failures detected — check $METRICS" >&2
exit 0
