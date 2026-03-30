#!/bin/bash
# Cost Tracker — Stop hook
# Appends session metrics to ~/.claude/metrics/costs.jsonl
# Passive logging only (exit 0).

source ~/.claude/hooks/hook-profile.sh && check_hook_profile "standard" || exit 0

INPUT=$(cat)

# Avoid loops
STOP_HOOK_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false' 2>/dev/null || echo "false")
if [ "$STOP_HOOK_ACTIVE" = "true" ]; then
    exit 0
fi

METRICS_DIR="$HOME/.claude/metrics"
mkdir -p "$METRICS_DIR"

TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
PROJECT=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")

# Build metrics record
jq -n \
    --arg ts "$TIMESTAMP" \
    --arg project "$PROJECT" \
    '{"timestamp":$ts,"project":$project,"event":"session_end"}' \
    >> "$METRICS_DIR/costs.jsonl" 2>/dev/null || true

exit 0
