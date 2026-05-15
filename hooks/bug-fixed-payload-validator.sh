#!/usr/bin/env bash
# BUG_FIXED payload validator — SubagentStop hook.
# Enforces structured reproducer_artifact {path, red_evidence, green_evidence}
# per AssertFlip (arXiv 2507.17542). DEBUG_RESOLVED env-only carve-out preserved.
#
# Mode = CLAUDE_BUGFIX_VALIDATOR_MODE ∈ {log (default), warn, strict}.
# enforces: rules/verdict-catalog.md (BUG_FIXED row)
set -uo pipefail

# shellcheck source=/dev/null
source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/bug_fixed_payload_validator.sh"

INPUT=$(cat)
STOP_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false' 2>/dev/null || echo false)
[[ "$STOP_ACTIVE" = "true" ]] && exit 0

TRANSCRIPT=$(echo "$INPUT" | jq -r '.transcript // .stop_transcript // ""' 2>/dev/null || echo "")
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // "unknown"' 2>/dev/null || echo unknown)
TASK_ID=$(echo "$INPUT" | jq -r '.task_id // "unknown"' 2>/dev/null || echo unknown)

# Path-safety: strict allow-list. Reject anything outside [A-Za-z0-9._-].
# Prevents traversal (`../etc/...`) through SESSION_ID / TASK_ID into the
# JSONL path and `mkdir -p` target.
sanitize_id() {
  local raw="$1"
  if [[ "$raw" =~ ^[A-Za-z0-9._-]+$ ]]; then
    printf '%s' "$raw"
  else
    printf 'unknown'
  fi
}
SESSION_ID=$(sanitize_id "$SESSION_ID")
TASK_ID=$(sanitize_id "$TASK_ID")

MODE="${CLAUDE_BUGFIX_VALIDATOR_MODE:-log}"
METRICS_DIR="${CLAUDE_METRICS_DIR:-${HOME}/.claude/metrics}"
JSONL="$METRICS_DIR/$SESSION_ID/bug-fixed-payload.jsonl"

# Parse verdict from transcript.
VERDICT=$(printf '%s' "$TRANSCRIPT" | grep -oE 'verdict:[[:space:]]*(BUG_FIXED|DEBUG_RESOLVED)' | head -1 | awk '{print $2}')
if [[ -z "$VERDICT" ]]; then
  exit 0  # No relevant verdict — nothing to enforce.
fi

SHAPE=$(_bfpv_classify "$TRANSCRIPT" "$VERDICT")

# Asymmetry: DEBUG_RESOLVED + env-only is always valid.
if [[ "$VERDICT" = "DEBUG_RESOLVED" && "$SHAPE" = "env_only" ]]; then
  _bfpv_emit_jsonl "$JSONL" "$TASK_ID" "$SHAPE" "pass"
  exit 0
fi

# BUG_FIXED + env-only is always rejected (in strict). In log/warn, audit-only.
case "$MODE" in
  log)
    _bfpv_emit_jsonl "$JSONL" "$TASK_ID" "$SHAPE" "log-only"
    exit 0 ;;
  warn)
    _bfpv_emit_jsonl "$JSONL" "$TASK_ID" "$SHAPE" "warn"
    [[ "$SHAPE" != "valid" ]] && echo "warn: BUG_FIXED payload shape=$SHAPE (rules/verdict-catalog.md)" >&2
    exit 0 ;;
  strict)
    if [[ "$SHAPE" = "valid" ]]; then
      _bfpv_emit_jsonl "$JSONL" "$TASK_ID" "$SHAPE" "pass"; exit 0
    fi
    _bfpv_emit_jsonl "$JSONL" "$TASK_ID" "$SHAPE" "reject"
    echo "BUG_FIXED payload $(_bfpv_reject_message "$SHAPE"). See rules/verdict-catalog.md BUG_FIXED row." >&2
    exit 2 ;;
  *) exit 0 ;;
esac
