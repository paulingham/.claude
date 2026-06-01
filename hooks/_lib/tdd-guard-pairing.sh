#!/usr/bin/env bash
# State pairing helpers: tdd-guard PreToolUse → SubagentStop forensics

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/harness-paths.sh"
_tdg_state_dir() { echo "$HARNESS_DATA/state"; }
_tdg_cursor_path() { echo "$(_tdg_state_dir)/tdd-guard-cursor-${1:-local}"; }
_tdg_snapshot_path() { echo "$(_tdg_state_dir)/tdd-guard-diff-snapshot-${1:-local}.json"; }
_tdg_events_path() { echo "$HARNESS_DATA/metrics/${CLAUDE_SESSION_ID:-local}/tdd-guard-events.jsonl"; }
_tdg_read_cursor() { cat "$(_tdg_cursor_path "$1")" 2>/dev/null || echo "0"; }
_tdg_write_cursor() { mkdir -p "$(_tdg_state_dir)"; echo "$2" > "$(_tdg_cursor_path "$1")"; }

_tdg_write_snapshot() {
  local task_id=$1 diff
  diff=$(git diff HEAD~1 HEAD --name-only 2>/dev/null | wc -l | tr -d ' ')
  mkdir -p "$(_tdg_state_dir)"
  python3 - "$diff" > "$(_tdg_snapshot_path "$task_id")" <<'PY'
import json, sys, time
print(json.dumps({"ts": int(time.time()), "diff_files": int(sys.argv[1])}))
PY
}
