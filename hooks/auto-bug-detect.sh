#!/bin/bash
# Auto Bug Detection — PostToolUse hook for Edit
# Detects bug-fix patterns from old_string/new_string diffs.
# Logs to ~/.claude/metrics/bugs-detected.jsonl
# Passive (exit 0).

source ~/.claude/hooks/hook-profile.sh && check_hook_profile "standard" || exit 0
source ~/.claude/hooks/loop-guard.sh && check_loop_guard "auto-bug-detect" || exit 0

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
TOOL_INPUT=$(echo "$INPUT" | jq -r '.tool_input // empty')

if [[ "$TOOL_NAME" != "Edit" ]]; then
    exit 0
fi

if [[ -z "$TOOL_INPUT" ]] || [[ -z "$FILE_PATH" ]]; then
    exit 0
fi

# Skip test files and config
case "$FILE_PATH" in
    *.test.*|*.spec.*|*__tests__/*|*/test/*|*/tests/*) exit 0 ;;
    *.md|*.json|*.yaml|*.yml|*.toml) exit 0 ;;
esac

# Extract old_string and new_string
OLD_STR=$(echo "$TOOL_INPUT" | python3 -c "import json,sys; d=json.loads(sys.stdin.read()); print(d.get('old_string',''))" 2>/dev/null)
NEW_STR=$(echo "$TOOL_INPUT" | python3 -c "import json,sys; d=json.loads(sys.stdin.read()); print(d.get('new_string',''))" 2>/dev/null)

if [[ -z "$OLD_STR" ]] || [[ -z "$NEW_STR" ]]; then
    exit 0
fi

METRICS_DIR="$HOME/.claude/metrics"
mkdir -p "$METRICS_DIR"

TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
PROJECT=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")

# Deduplication: skip if same file+category logged in last 5 minutes
DEDUP_DIR="/tmp/claude-hook-guard/bug-detect"
mkdir -p -m 700 "$DEDUP_DIR"

log_bug() {
    local category="$1"
    local summary="$2"
    local dedup_key="${FILE_PATH}_${category}"
    local dedup_hash=$(echo "$dedup_key" | md5 -q 2>/dev/null || echo "$dedup_key" | md5sum 2>/dev/null | cut -d' ' -f1)
    local dedup_file="$DEDUP_DIR/$dedup_hash"

    # Check 5-minute dedup window
    if [[ -f "$dedup_file" ]]; then
        local last=$(cat "$dedup_file" 2>/dev/null)
        local now=$(date +%s)
        if [[ $((now - last)) -lt 300 ]]; then
            return
        fi
    fi
    date +%s > "$dedup_file"

    jq -n \
        --arg ts "$TIMESTAMP" \
        --arg file "$FILE_PATH" \
        --arg cat "$category" \
        --arg summary "$summary" \
        --arg project "$PROJECT" \
        '{"timestamp":$ts,"file":$file,"category":$cat,"summary":$summary,"project":$project}' \
        >> "$METRICS_DIR/bugs-detected.jsonl" 2>/dev/null || true
}

# Detect patterns: check if new_string has something old_string lacks

# Error handling added
if echo "$NEW_STR" | grep -qE '(try\s*\{|\.catch\(|rescue\b|except\b)' && ! echo "$OLD_STR" | grep -qE '(try\s*\{|\.catch\(|rescue\b|except\b)'; then
    log_bug "error-handling" "added error handling"
fi

# Null safety added
if echo "$NEW_STR" | grep -qE '(\?\.|!= null|\?\?|\.nil\?|is not None)' && ! echo "$OLD_STR" | grep -qE '(\?\.|!= null|\?\?|\.nil\?|is not None)'; then
    log_bug "null-safety" "added null safety check"
fi

# Guard clause added
if echo "$NEW_STR" | grep -qE '^\s*(if|unless).*return\b' && ! echo "$OLD_STR" | grep -qE '^\s*(if|unless).*return\b'; then
    log_bug "guard-clause" "added guard clause"
fi

# Operator fix
if echo "$OLD_STR" | grep -qE '==[^=]' && echo "$NEW_STR" | grep -qE '==='; then
    log_bug "operator-fix" "fixed == to ==="
fi

# Missing async/await
if echo "$NEW_STR" | grep -qE '\bawait\b' && ! echo "$OLD_STR" | grep -qE '\bawait\b'; then
    log_bug "async-fix" "added missing await"
fi

# Missing import
if echo "$NEW_STR" | grep -qE '^\s*(import|require|from)\b' && ! echo "$OLD_STR" | grep -qE '^\s*(import|require|from)\b'; then
    log_bug "missing-import" "added missing import"
fi

exit 0
