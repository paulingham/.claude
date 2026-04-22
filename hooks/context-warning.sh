#!/usr/bin/env bash
# Context Warning — PostToolUse hook (all tools)
# Reads context usage from $HOME/.claude/state/ctx-percent (written by statusline)
# Injects warnings at thresholds: 65% used = WARNING, 75% used = CRITICAL
# Advisory only (exit 0). Debounced to avoid spam.

# Hook profile
source ~/.claude/hooks/hook-profile.sh && check_hook_profile "standard" || exit 0
# shellcheck source=_lib/state-dir.sh
source "$(dirname "${BASH_SOURCE[0]}")/_lib/state-dir.sh"
_ensure_state_dir

CTX_FILE=$(_state_path "ctx-percent-${PPID}")

# Skip if no context data available
if [[ ! -f "$CTX_FILE" ]]; then
    exit 0
fi

CTX_PCT=$(cat "$CTX_FILE" 2>/dev/null | tr -d '[:space:]')

# Validate it's a number
if ! [[ "$CTX_PCT" =~ ^[0-9]+$ ]]; then
    exit 0
fi

# Below warning threshold — exit silently
if [[ "$CTX_PCT" -lt 65 ]]; then
    exit 0
fi

# Debounce: use a counter file to avoid spamming
HOOK_GUARD_DIR=$(_state_path "hook-guard")
mkdir -p -m 700 "$HOOK_GUARD_DIR"
DEBOUNCE_FILE="$HOOK_GUARD_DIR/context-warning-count"

COUNT=0
if [[ -f "$DEBOUNCE_FILE" ]]; then
    COUNT=$(cat "$DEBOUNCE_FILE" 2>/dev/null | tr -d '[:space:]')
    [[ "$COUNT" =~ ^[0-9]+$ ]] || COUNT=0
fi

COUNT=$((COUNT + 1))
( umask 077 && printf '%s\n' "$COUNT" > "$DEBOUNCE_FILE" )

# Warn every 10 tool calls in WARNING zone (65-74%), every 5 in CRITICAL zone (75+)
if [[ "$CTX_PCT" -ge 75 ]]; then
    INTERVAL=5
else
    INTERVAL=10
fi

if [[ $((COUNT % INTERVAL)) -ne 0 ]]; then
    exit 0
fi

# Emit warning
REMAINING=$((100 - CTX_PCT))

if [[ "$CTX_PCT" -ge 75 ]]; then
    echo "CRITICAL CONTEXT WARNING: ${CTX_PCT}% used (${REMAINING}% remaining). Save pipeline state NOW and consider compacting or starting a new session." >&2
else
    echo "CONTEXT WARNING: ${CTX_PCT}% used (${REMAINING}% remaining). Consider completing the current pipeline phase soon." >&2
fi

exit 0
