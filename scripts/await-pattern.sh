#!/usr/bin/env bash
# await-pattern.sh — await a regex match in a log file with timeout + max_lines bound.
# Usage: await-pattern.sh <log_path> <regex> <timeout_seconds> <max_lines>
# Exit:  0=match, 124=timeout, 130=SIGINT, 1=bad-args/max_lines/missing-log.
# Emits one JSONL record (await_match|await_timeout) to
#   $HOME/.claude/metrics/${CLAUDE_SESSION_ID:-local-$$}/await-events.jsonl

[[ "${BASH_SOURCE[0]}" == "$0" ]] || return 0
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
. "$SCRIPT_DIR/_lib/await-pattern-lib.sh"
# shellcheck source=/dev/null
. "$SCRIPT_DIR/_lib/await-pattern-emit.sh"

_aw_validate_args "$@" || exit 1
LOG="$1" RX="$2" TO="$3" MAX="$4"
_aw_validate_log_path "$LOG" || exit 1

OUT="$(_aw_resolve_metrics_path)"
SID="${CLAUDE_SESSION_ID:-local-$$}" TID="${CLAUDE_PIPELINE_TASK_ID:-}"
START=$(date +%s) SCANNED=0 TAIL_PID=0 WD_PID=0 EMITTED=0 FIFO=""

_aw_setup_fifo() { FIFO="$(mktemp -u "${TMPDIR:-/tmp}/aw.fifo.XXXXXX")"; mkfifo "$FIFO" || exit 1; }
_aw_cleanup() { exec 3<&- 2>/dev/null || true; kill -TERM "$WD_PID" "$TAIL_PID" 2>/dev/null || true; wait 2>/dev/null || true; [ -n "$FIFO" ] && rm -f "$FIFO"; return 0; }
_aw_emit_to() { [ "$EMITTED" -eq 1 ] && return 0; EMITTED=1; local el=$(( $(date +%s) - START )); _aw_emit_timeout "$OUT" "$(_aw_now_ts)" "$SID" "$TID" "$LOG" "$RX" "$TO" "$el" "$SCANNED"; }
_aw_emit_mt() { EMITTED=1; local el=$(( $(date +%s) - START )); _aw_emit_match "$OUT" "$(_aw_now_ts)" "$SID" "$TID" "$LOG" "$RX" "$TO" "$el" "$1"; }
_aw_on_int() { _aw_emit_to; _aw_cleanup; exit 130; }
trap _aw_on_int INT TERM

_aw_setup_fifo
tail -n +1 -f "$LOG" > "$FIFO" 2>/dev/null &
TAIL_PID=$!
( sleep "$TO"; kill -TERM "$TAIL_PID" 2>/dev/null ) &
WD_PID=$!
exec 3< "$FIFO"

while IFS= read -r raw <&3; do
  SCANNED=$((SCANNED+1))
  line="$(printf '%s' "$raw" | _aw_strip_ansi)"
  [ "$SCANNED" -gt "$MAX" ] && { _aw_cleanup; exit 1; }
  if printf '%s\n' "$line" | grep -qE -- "$RX"; then
    _aw_emit_mt "$line"; _aw_cleanup; exit 0
  fi
done

_aw_emit_to; _aw_cleanup; exit 124
