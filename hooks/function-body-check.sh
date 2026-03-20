#!/bin/bash
# Function Body Length Check — PostToolUse hook (runs alongside code-shape-check.sh)
# Checks TypeScript/JavaScript files for function bodies exceeding 5 lines.
# Uses a heuristic: counts lines between function opening { and closing }.
# BLOCK mode (exit 2) — blocks writes that create functions exceeding limit.

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
if [[ "$FILE_PATH" =~ /__tests__/ ]] || [[ "$FILE_PATH" =~ /test/ ]] || [[ "$FILE_PATH" =~ /tests/ ]] || [[ "$FILE_PATH" =~ /e2e/ ]]; then
    exit 0
fi

# Skip config files and node_modules
if [[ "$FILE_PATH" =~ \.config\.(ts|js)$ ]] || [[ "$FILE_PATH" =~ (tailwind|babel|metro|jest|eslint|prettier) ]] || [[ "$FILE_PATH" =~ /node_modules/ ]]; then
    exit 0
fi

# Skip if file doesn't exist
if [[ ! -f "$FILE_PATH" ]]; then
    exit 0
fi

# Heuristic function body counter using awk
# Counts lines between { and } for function/method declarations
# Reports any function body exceeding 5 lines
VIOLATIONS=$(awk '
BEGIN { depth=0; fname=""; fline=0; body=0; violations="" }
/^[[:space:]]*(export[[:space:]]+)?(async[[:space:]]+)?function[[:space:]]+[a-zA-Z]/ {
    fname=$0; sub(/^[[:space:]]+/, "", fname); fline=NR; body=0; next
}
/^[[:space:]]*(export[[:space:]]+)?const[[:space:]]+[a-zA-Z]+[[:space:]]*=[[:space:]]*(async[[:space:]]*)?\(/ {
    fname=$0; sub(/^[[:space:]]+/, "", fname); fline=NR; body=0; next
}
fname != "" && /{/ { depth++ }
fname != "" && /}/ {
    depth--
    if (depth <= 0) {
        if (body > 5) {
            violations = violations "  Line " fline ": " body " lines (limit: 5)\n"
        }
        fname=""; body=0; depth=0
    }
}
fname != "" && depth > 0 { body++ }
END { printf "%s", violations }
' "$FILE_PATH")

if [[ -n "$VIOLATIONS" ]]; then
    echo "" >&2
    echo "FUNCTION BODY WARNING: $FILE_PATH has functions exceeding 5-line limit:" >&2
    echo "$VIOLATIONS" >&2
    echo "Consider extracting helper functions or decomposing." >&2
    echo "" >&2
    # Exit 2 = HARD BLOCK (must fix before continuing)
    exit 2
fi

exit 0
