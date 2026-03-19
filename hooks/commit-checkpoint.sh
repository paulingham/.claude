#!/bin/bash
# Commit Checkpoint — PreToolUse hook for git commit commands
# Lightweight quality check: warns on issues but does not block.
# Catches problems earlier than the PR quality gate.

TOOL_NAME="${CLAUDE_TOOL_NAME:-}"
COMMAND="${CLAUDE_COMMAND:-}"

# Only check Bash commands
if [[ "$TOOL_NAME" != "Bash" ]]; then
    exit 0
fi

# Only check git commit commands
if [[ ! "$COMMAND" =~ "git commit" ]]; then
    exit 0
fi

# Skip if this is an amend (user explicitly requested)
if [[ "$COMMAND" =~ "--amend" ]]; then
    exit 0
fi

echo "COMMIT CHECKPOINT: Quick pre-commit check..." >&2

WARNINGS=0

# Check 1: Staged source files over 50 lines
STAGED_FILES=$(git diff --cached --name-only 2>/dev/null | grep -E '\.(ts|tsx|js|jsx)$' | grep -vE '\.(test|spec)\.' | grep -vE '(__tests__|/test/|/tests/|/e2e/)' | grep -vE '\.(config)\.' | grep -vE '(tailwind|babel|metro|jest|eslint|prettier)' || true)

for file in $STAGED_FILES; do
    if [[ -f "$file" ]]; then
        LINES=$(wc -l < "$file" | tr -d ' ')
        if [[ "$LINES" -gt 50 ]]; then
            echo "  WARNING: $file has $LINES lines (limit: 50)" >&2
            WARNINGS=1
        fi
    fi
done

# Check 2: Fast type check (if TypeScript project)
if [[ -f "package.json" ]] && grep -q '"typescript"' package.json 2>/dev/null; then
    if command -v npx &> /dev/null; then
        TSC_OUTPUT=$(npx tsc --noEmit 2>&1) || {
            echo "  WARNING: TypeScript type errors detected" >&2
            echo "$TSC_OUTPUT" | tail -5 >&2
            WARNINGS=1
        }
        if [[ $WARNINGS -eq 0 ]]; then
            echo "  PASSED: TypeScript type check clean" >&2
        fi
    fi
fi

if [[ $WARNINGS -eq 1 ]]; then
    echo "COMMIT CHECKPOINT: Warnings found — review before creating PR" >&2
fi

# Always exit 0 — checkpoint is advisory, never blocking
exit 0
