#!/usr/bin/env bash
# Cyclomatic Complexity Check — PostToolUse ADVISORY hook
# Fires after Write/Edit on source files (not tests, not config).
# Warns (exit 0) if cyclomatic complexity exceeds 5. Never hard-blocks.
# Supports: .ts/.tsx/.js/.jsx/.rb/.py/.go

# Hook profile and loop guard
source ~/.claude/hooks/hook-profile.sh && check_hook_profile "standard" || exit 0
source ~/.claude/hooks/loop-guard.sh && check_loop_guard "cc-check" || exit 0

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# Only check if we have a file path
if [[ -z "$FILE_PATH" ]]; then
    exit 0
fi

# Only check source files
case "$FILE_PATH" in
    *.ts|*.tsx|*.js|*.jsx|*.rb|*.py|*.go) ;;
    *) exit 0 ;;
esac

# Skip test files (all languages)
BASENAME=$(basename "$FILE_PATH")
if [[ "$FILE_PATH" =~ \.(test|spec)\.(ts|tsx|js|jsx)$ ]]; then
    exit 0
fi
if [[ "$FILE_PATH" =~ _spec\.rb$ ]]; then
    exit 0
fi
if [[ "$BASENAME" =~ ^test_.*\.py$ ]] || [[ "$BASENAME" =~ _test\.py$ ]]; then
    exit 0
fi
if [[ "$FILE_PATH" =~ _test\.go$ ]]; then
    exit 0
fi
if [[ "$FILE_PATH" =~ /__tests__/ ]] || [[ "$FILE_PATH" =~ /test/ ]] || [[ "$FILE_PATH" =~ /tests/ ]] || [[ "$FILE_PATH" =~ /e2e/ ]] || [[ "$FILE_PATH" =~ /spec/ ]]; then
    exit 0
fi

# Skip if file doesn't exist
if [[ ! -f "$FILE_PATH" ]]; then
    exit 0
fi

CC_OUTPUT=""

case "$FILE_PATH" in
    *.ts|*.tsx|*.js|*.jsx)
        if command -v npx &> /dev/null && npx eslint --version &> /dev/null 2>&1; then
            CC_OUTPUT=$(npx eslint --rule '{"complexity": ["error", 5]}' --no-eslintrc "$FILE_PATH" 2>&1) || true
        else
            exit 0
        fi
        ;;
    *.rb)
        if command -v rubocop &> /dev/null; then
            CC_OUTPUT=$(rubocop --only Metrics/CyclomaticComplexity "$FILE_PATH" 2>&1) || true
        else
            exit 0
        fi
        ;;
    *.py)
        if command -v radon &> /dev/null; then
            CC_OUTPUT=$(radon cc -s -n C "$FILE_PATH" 2>&1) || true
        else
            exit 0
        fi
        ;;
    *.go)
        if command -v gocyclo &> /dev/null; then
            CC_OUTPUT=$(gocyclo -over 5 "$FILE_PATH" 2>&1) || true
        else
            exit 0
        fi
        ;;
esac

if [[ -n "$CC_OUTPUT" ]]; then
    echo "" >&2
    echo "CC Warning: Cyclomatic complexity violation in $FILE_PATH (max 5). Consider decomposing." >&2
    echo "$CC_OUTPUT" >&2
    echo "" >&2
fi

exit 0
