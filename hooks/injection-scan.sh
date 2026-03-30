#!/bin/bash
# Injection Scan — PostToolUse hook for Write and Edit
# Scans content of files written under ~/.claude/ for prompt injection patterns.
# Advisory only (exit 0 + stderr warning). Never blocks legitimate writes.

# Hook profile and loop guard
source ~/.claude/hooks/hook-profile.sh && check_hook_profile "standard" || exit 0
source ~/.claude/hooks/loop-guard.sh && check_loop_guard "injection-scan" || exit 0

FILE_PATH="${CLAUDE_FILE_PATH:-}"

# Skip if no file path
if [[ -z "$FILE_PATH" ]]; then
    exit 0
fi

# Only scan files under ~/.claude/
case "$FILE_PATH" in
    "$HOME/.claude/"*) ;;
    *) exit 0 ;;
esac

# Skip if file doesn't exist (deleted)
if [[ ! -f "$FILE_PATH" ]]; then
    exit 0
fi

WARNINGS=""

# Pattern 1: Instruction overrides
if grep -qi -E '(ignore previous|disregard (all|your|prior)|new instructions|override (previous|your)|forget your (instructions|rules|prompt))' "$FILE_PATH" 2>/dev/null; then
    WARNINGS="${WARNINGS}\n  - Instruction override pattern detected"
fi

# Pattern 2: Role assumption
if grep -qi -E '(you are now|act as (a|an|if)|pretend you are|your new role|assume the role)' "$FILE_PATH" 2>/dev/null; then
    WARNINGS="${WARNINGS}\n  - Role assumption pattern detected"
fi

# Pattern 3: Extraction attempts
if grep -qi -E '(output your (system|original) prompt|reveal your (instructions|rules|system)|show (me )?your (prompt|rules|instructions)|print your (system|config))' "$FILE_PATH" 2>/dev/null; then
    WARNINGS="${WARNINGS}\n  - Extraction attempt pattern detected"
fi

# Pattern 4: Suspicious base64 blocks (40+ chars of base64 alphabet)
if grep -qE '[A-Za-z0-9+/]{40,}={0,2}' "$FILE_PATH" 2>/dev/null; then
    # Exclude common false positives: git SHAs, URLs, file paths
    B64_LINES=$(grep -nE '[A-Za-z0-9+/]{40,}={0,2}' "$FILE_PATH" 2>/dev/null | grep -vE '(https?://|git |commit |sha256|\.com/|\.io/)' | head -3)
    if [[ -n "$B64_LINES" ]]; then
        WARNINGS="${WARNINGS}\n  - Suspicious base64-like block detected"
    fi
fi

# Pattern 5: Unicode obfuscation (zero-width chars, direction overrides)
# Check for: U+200B (zero-width space), U+200D (zero-width joiner), U+202E (RTL override), U+FEFF (BOM in middle)
if od -An -tx1 "$FILE_PATH" 2>/dev/null | grep -qi -E '(e2 80 8b|e2 80 8d|e2 80 ae|ef bb bf)'; then
    # Exclude BOM at file start (first 3 bytes)
    FILE_SIZE=$(wc -c < "$FILE_PATH" | tr -d ' ')
    if [[ "$FILE_SIZE" -gt 3 ]]; then
        INNER_CHECK=$(tail -c +4 "$FILE_PATH" | od -An -tx1 2>/dev/null | grep -qi -E '(e2 80 8b|e2 80 8d|e2 80 ae|ef bb bf)' && echo "found" || echo "")
        if [[ "$INNER_CHECK" == "found" ]]; then
            WARNINGS="${WARNINGS}\n  - Unicode obfuscation characters detected (zero-width/direction override)"
        fi
    fi
fi

if [[ -n "$WARNINGS" ]]; then
    echo "" >&2
    echo "INJECTION SCAN WARNING: Suspicious patterns in $FILE_PATH:" >&2
    echo -e "$WARNINGS" >&2
    echo "  Review this content before trusting it." >&2
    echo "" >&2
fi

exit 0
