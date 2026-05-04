#!/usr/bin/env bash
# Code Shape Check — PostToolUse BLOCKING hook
# Fires after Write/Edit on source files (not tests, not config)
# HARD BLOCKS (exit 2) if file exceeds line limit — forces immediate decomposition
# Supports: .ts/.tsx/.js/.jsx/.rb/.py/.go

# Hook profile and loop guard
source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "PostToolUse:${TOOL_NAME:-Write}"
trap 'log_hook_event $?' EXIT

source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/hook-profile.sh" && check_hook_profile "standard" || exit 0
source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/loop-guard.sh" && check_loop_guard "code-shape-check" || exit 0

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
# Safety-net cap — catches genuinely runaway files. Cohesion is the design
# rule (see rules/core.md § Code Shape Rules); this hook only blocks clearly
# broken output, not normal cohesive functions/files.
LINE_LIMIT="${CLAUDE_FILE_LINE_LIMIT:-300}"

# Only check if we have a file path
if [[ -z "$FILE_PATH" ]]; then
    exit 0
fi

# Only check source files
case "$FILE_PATH" in
    *.ts|*.tsx|*.js|*.jsx|*.rb|*.py|*.go) ;;
    *) exit 0 ;;
esac

# Skip JS/TS test files
if [[ "$FILE_PATH" =~ \.(test|spec)\.(ts|tsx|js|jsx)$ ]]; then
    exit 0
fi

# Skip Ruby test files (_spec.rb)
if [[ "$FILE_PATH" =~ _spec\.rb$ ]]; then
    exit 0
fi

# Skip Python test files (test_*.py, *_test.py)
BASENAME=$(basename "$FILE_PATH")
if [[ "$BASENAME" =~ ^test_.*\.py$ ]] || [[ "$BASENAME" =~ _test\.py$ ]]; then
    exit 0
fi

# Skip Go test files (_test.go)
if [[ "$FILE_PATH" =~ _test\.go$ ]]; then
    exit 0
fi

# Skip test directories
if [[ "$FILE_PATH" =~ /__tests__/ ]] || [[ "$FILE_PATH" =~ /test/ ]] || [[ "$FILE_PATH" =~ /tests/ ]] || [[ "$FILE_PATH" =~ /e2e/ ]] || [[ "$FILE_PATH" =~ /spec/ ]]; then
    exit 0
fi

# Skip JS/TS config files
if [[ "$FILE_PATH" =~ \.config\.(ts|js)$ ]]; then
    exit 0
fi
if [[ "$FILE_PATH" =~ (tailwind|babel|metro|jest|eslint|prettier) ]]; then
    exit 0
fi
if [[ "$FILE_PATH" =~ /node_modules/ ]]; then
    exit 0
fi

# Skip Ruby config files
if [[ "$FILE_PATH" =~ config/.*\.rb$ ]]; then
    exit 0
fi

# Skip Python config files
if [[ "$BASENAME" == "conftest.py" ]] || [[ "$BASENAME" == "setup.py" ]] || [[ "$BASENAME" == "__init__.py" ]]; then
    exit 0
fi

# Skip if file doesn't exist (deleted)
if [[ ! -f "$FILE_PATH" ]]; then
    exit 0
fi

# Count lines
LINE_COUNT=$(wc -l < "$FILE_PATH" | tr -d ' ')

if [[ "$LINE_COUNT" -gt "$LINE_LIMIT" ]]; then
    echo "" >&2
    echo "CODE SHAPE VIOLATION: $FILE_PATH has $LINE_COUNT lines (limit: $LINE_LIMIT)" >&2
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
