#!/usr/bin/env bash
# Observation-length Cap — PostToolUse hook on Edit (advisory at v2.1.140, log-only).
#
# Measures per-write payload size against a soft cap on writes to
# session-memory observation files (build-test.md, patterns.md, fragility.md).
# Emits one JSONL line per qualifying Edit to
#   metrics/{session-id}/observation-length-cap.jsonl
# with `would_truncate` set when estimated_tokens > cap_tokens. NO truncation
# happens at v2.1.140 — the flag names the counterfactual under enforcement.
#
# 250-token cap rationale: measured baseline shows a typical 3-bullet session-
# memory entry runs ≈ 150-225 tokens (≈ 600-900 chars via the canonical chars/4
# estimate used in hooks/_lib/tool-output-bytes-emit.py). 250 tokens is a
# deliberately tight initial target; tight caps surface real over-runs in the
# log immediately rather than burying them behind a generous threshold.
#
# event := one JSONL line in metrics/{session}/observation-length-cap.jsonl.
# Recompute trigger: rolling window of last 50 events with >10 (>20%)
#   would_truncate=true retunes the cap upward to 400 before any enforcement
#   flip is considered.
# Flip-to-enforcement criteria: 50 events recorded AND <20% would_truncate
#   ratio over the rolling window of 50. If the ratio is ≥20%, retune to 400
#   first and re-measure — do not flip until the new cap shows <20%.
#
# See: protocols/_proposals/2026-05-14-observation-length-cap.md
#
# enforces: protocols/_proposals/2026-05-14-observation-length-cap.md
# protects: session-memory growth, observation injection budget

set -u

# Always exit 0 (log-only invariant).
trap 'exit 0' EXIT ERR

INPUT=$(cat)

# Extract fields (portable BSD/GNU; no awk capture).
FILE_PATH=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null || echo "")
NEW_STRING=$(printf '%s' "$INPUT" | jq -r '.tool_input.new_string // empty' 2>/dev/null || echo "")
AGENT_ROLE="${CLAUDE_AGENT_ROLE:-unknown}"

[[ -z "$FILE_PATH" ]] && exit 0

# Path filter: only watch session-memory observation files
# (session-memory/*/build-test.md|patterns.md|fragility.md).
case "$FILE_PATH" in
    */session-memory/*/build-test.md|*/session-memory/*/patterns.md|*/session-memory/*/fragility.md)
        ;;
    *)
        exit 0
        ;;
esac

# Session-id cascade (verbatim from hooks/observation-capture.sh:56-65).
# shellcheck source=_lib/state-dir.sh
# shellcheck disable=SC1091
source "$(dirname "${BASH_SOURCE[0]}")/_lib/state-dir.sh"
_ensure_state_dir
SESSION_FILE=$(_state_path "session-${PPID}")
if [[ -n "${CLAUDE_SESSION_ID:-}" ]]; then
    SESSION_ID="$CLAUDE_SESSION_ID"
elif [[ -f "$SESSION_FILE" ]]; then
    SESSION_ID=$(cat "$SESSION_FILE")
else
    SESSION_ID=$(uuidgen 2>/dev/null || echo "sess-${RANDOM}-${RANDOM}")
    printf '%s\n' "$SESSION_ID" | _state_write "session-${PPID}"
fi

# Compute char count via wc -c (portable).
CHAR_COUNT=$(printf '%s' "$NEW_STRING" | wc -c | tr -d ' ')
[[ -z "$CHAR_COUNT" ]] && CHAR_COUNT=0
CAP_TOKENS=250
ESTIMATED_TOKENS=$(( CHAR_COUNT / 4 ))
if [[ "$ESTIMATED_TOKENS" -gt "$CAP_TOKENS" ]]; then
    WOULD_TRUNCATE=true
else
    WOULD_TRUNCATE=false
fi

METRICS_DIR="$HOME/.claude/metrics/$SESSION_ID"
mkdir -p "$METRICS_DIR" 2>/dev/null || exit 0
OUT_FILE="$METRICS_DIR/observation-length-cap.jsonl"

TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
LINE=$(jq -cn \
    --arg ts "$TS" \
    --arg agent_role "$AGENT_ROLE" \
    --arg file_path "$FILE_PATH" \
    --argjson char_count "$CHAR_COUNT" \
    --argjson estimated_tokens "$ESTIMATED_TOKENS" \
    --argjson would_truncate "$WOULD_TRUNCATE" \
    --argjson cap_tokens "$CAP_TOKENS" \
    '{ts: $ts, agent_role: $agent_role, file_path: $file_path, char_count: $char_count, estimated_tokens: $estimated_tokens, would_truncate: $would_truncate, cap_tokens: $cap_tokens}' \
    2>/dev/null) || exit 0

printf '%s\n' "$LINE" >> "$OUT_FILE"
exit 0
