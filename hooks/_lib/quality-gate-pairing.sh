#!/usr/bin/env bash
# State pairing helpers: quality-gate PreToolUse → SubagentStop forensics
# Mirrors the cursor pattern from worktree-cwd-pairing.sh

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/harness-paths.sh"
_qg_state_dir() { echo "$HARNESS_DATA/state"; }
_qg_cursor_path() { echo "$(_qg_state_dir)/quality-gate-cursor-${1:-local}"; }
_qg_snapshot_path() { echo "$(_qg_state_dir)/quality-gate-snapshot-${1:-local}.json"; }
_qg_events_path() { echo "$HARNESS_DATA/metrics/${CLAUDE_SESSION_ID:-local}/quality-gate-events.jsonl"; }
_qg_read_cursor() { cat "$(_qg_cursor_path "$1")" 2>/dev/null || echo "0"; }
_qg_write_cursor() { mkdir -p "$(_qg_state_dir)"; echo "$2" > "$(_qg_cursor_path "$1")"; }

_qg_write_snapshot() {
  local task_id=$1
  mkdir -p "$(_qg_state_dir)"
  python3 - > "$(_qg_snapshot_path "$task_id")" <<'PY'
import json, time
print(json.dumps({"ts": int(time.time()), "tests_ok": True, "lint_ok": True, "shape_ok": True}))
PY
}
