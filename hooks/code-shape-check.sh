#!/bin/bash
# Code Shape Check — PostToolUse BLOCKING hook
# Fires after Write/Edit on .ts/.tsx/.js/.jsx source files (not tests, not config)
# HARD BLOCKS (exit 2) if file exceeds 50 lines — forces immediate decomposition

# Hook profile and loop guard
source ~/.claude/hooks/hook-profile.sh && check_hook_profile "standard" || exit 0
source ~/.claude/hooks/loop-guard.sh && check_loop_guard "code-shape-check" || exit 0

FILE_PATH="${CLAUDE_FILE_PATH:-}"

# Only check if we have a file path
if [[ -z "$FILE_PATH" ]]; then
    exit 0
fi

# Only check source files (.ts, .tsx, .js, .jsx)
if [[ ! "$FILE_PATH" =~ \.(ts|tsx|js|jsx)$ ]]; then
    exit 0
fi

# Skip test files
if [[ "$FILE_PATH" =~ \.(test|spec)\.(ts|tsx|js|jsx)$ ]]; then
    exit 0
fi
if [[ "$FILE_PATH" =~ /__tests__/ ]]; then
    exit 0
fi
if [[ "$FILE_PATH" =~ /test/ ]] || [[ "$FILE_PATH" =~ /tests/ ]]; then
    exit 0
fi
if [[ "$FILE_PATH" =~ /e2e/ ]]; then
    exit 0
fi

# Skip config files
if [[ "$FILE_PATH" =~ \.config\.(ts|js)$ ]]; then
    exit 0
fi
if [[ "$FILE_PATH" =~ (tailwind|babel|metro|jest|eslint|prettier) ]]; then
    exit 0
fi
if [[ "$FILE_PATH" =~ /node_modules/ ]]; then
    exit 0
fi

# Skip if file doesn't exist (deleted)
if [[ ! -f "$FILE_PATH" ]]; then
    exit 0
fi

# Count lines
LINE_COUNT=$(wc -l < "$FILE_PATH" | tr -d ' ')

if [[ "$LINE_COUNT" -gt 50 ]]; then
    echo "" >&2
    echo "CODE SHAPE VIOLATION: $FILE_PATH has $LINE_COUNT lines (limit: 50)" >&2
    echo "" >&2
    echo "BLOCKED: Decompose this file before continuing." >&2
    echo "Options:" >&2
    echo "  - Extract functions into separate modules" >&2
    echo "  - Split component into container/presenter" >&2
    echo "  - Extract custom hooks into useXxx files" >&2
    echo "  - Move constants/config to dedicated files" >&2
    echo "" >&2
    exit 2  # HARD BLOCK
fi

exit 0
