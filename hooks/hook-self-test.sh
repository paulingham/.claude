#!/usr/bin/env bash
# Hook self-test — verifies registered PreToolUse hooks at SessionStart
# enforces: rules/core.md:Iron Laws
# protects: pipeline, all-skills
# self-test: skip
# Scope: registration + early-exit shape only. Fast-exit payloads, respects # self-test: skip.
#
# Rate-limited: runs at most once per CLAUDE_HOOK_SELF_TEST_INTERVAL_HOURS
# (default 24) via a sentinel at $HOME/.claude/.hook-self-test-state.json.
# Escape hatch: CLAUDE_DISABLE_HOOK_SELF_TEST=1 → fast-exit 0.

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

# Escape hatch — fast-exit before any work.
[[ "${CLAUDE_DISABLE_HOOK_SELF_TEST:-0}" == "1" ]] && exit 0

# Rate-limit gate. Sentinel: $HOME/.claude/.hook-self-test-state.json
# {"last_run": <epoch_seconds>}. Skip when within the configured interval.
SELF_TEST_SENTINEL="${HOME}/.claude/.hook-self-test-state.json"
SELF_TEST_INTERVAL_HOURS="${CLAUDE_HOOK_SELF_TEST_INTERVAL_HOURS:-24}"
if [[ -f "$SELF_TEST_SENTINEL" ]]; then
  NOW_EPOCH="$(date +%s)"
  LAST_RUN="$(python3 -c '
import json, sys
try:
    print(int(json.load(open(sys.argv[1])).get("last_run", 0)))
except Exception:
    print(0)
' "$SELF_TEST_SENTINEL" 2>/dev/null || echo 0)"
  INTERVAL_SECONDS=$(( SELF_TEST_INTERVAL_HOURS * 3600 ))
  if (( NOW_EPOCH - LAST_RUN < INTERVAL_SECONDS )); then
    exit 0
  fi
fi

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

# Update sentinel even on partial failure — don't loop-retry next session.
mkdir -p "$(dirname "$SELF_TEST_SENTINEL")" 2>/dev/null
python3 - "$SELF_TEST_SENTINEL" <<'PY' 2>/dev/null
import json, os, sys, time
path = sys.argv[1]
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "w") as fh:
    json.dump({"last_run": int(time.time())}, fh)
PY

exit 0
