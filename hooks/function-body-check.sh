#!/usr/bin/env bash
# Function Body Length Check — PostToolUse hook (runs alongside code-shape-check.sh)
# Checks source files for function bodies exceeding the line limit.
# Uses language-specific heuristics to detect function boundaries.
# Supports: .ts/.tsx/.js/.jsx/.rb/.py/.go
# ADVISORY mode (exit 0) — warns but does not block. Pre-existing violations exist
# in the codebase (documented in project CLAUDE.md Known Limitations) so this hook
# surfaces shape drift as a warning rather than a hard block.

# Hook profile and loop guard
source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "PostToolUse:${TOOL_NAME:-Write}"
trap 'log_hook_event $?' EXIT

source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/hook-profile.sh" && check_hook_profile "standard" || exit 0
source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/loop-guard.sh" && check_loop_guard "function-body-check" || exit 0

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
FUNC_LIMIT="${CLAUDE_FUNCTION_LINE_LIMIT:-8}"

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

# Skip config files and node_modules
if [[ "$FILE_PATH" =~ \.config\.(ts|js)$ ]] || [[ "$FILE_PATH" =~ (tailwind|babel|metro|jest|eslint|prettier) ]] || [[ "$FILE_PATH" =~ /node_modules/ ]]; then
    exit 0
fi
if [[ "$FILE_PATH" =~ config/.*\.rb$ ]]; then
    exit 0
fi
if [[ "$BASENAME" == "conftest.py" ]] || [[ "$BASENAME" == "setup.py" ]] || [[ "$BASENAME" == "__init__.py" ]]; then
    exit 0
fi

# Skip if file doesn't exist
if [[ ! -f "$FILE_PATH" ]]; then
    exit 0
fi

# Select parser based on file extension
VIOLATIONS=""

case "$FILE_PATH" in
    *.ts|*.tsx|*.js|*.jsx)
        # JS/TS: count lines between { and } for function declarations
        VIOLATIONS=$(awk -v limit="$FUNC_LIMIT" '
BEGIN { depth=0; fname=""; fline=0; body=0; violations="" }
/^[[:space:]]*(export[[:space:]]+)?(async[[:space:]]+)?function[[:space:]]+[a-zA-Z]/ {
    fname=$0; sub(/^[[:space:]]+/, "", fname); fline=NR; body=0
    if (/{/) { depth++ }
    next
}
/^[[:space:]]*(export[[:space:]]+)?const[[:space:]]+[a-zA-Z]+[[:space:]]*=[[:space:]]*(async[[:space:]]*)?\(/ {
    fname=$0; sub(/^[[:space:]]+/, "", fname); fline=NR; body=0; next
}
fname != "" && /{/ { depth++ }
fname != "" && /}/ {
    depth--
    if (depth <= 0) {
        if (body > limit) {
            violations = violations "  Line " fline ": " body " lines (limit: " limit ")\n"
        }
        fname=""; body=0; depth=0
    }
}
fname != "" && depth > 0 { body++ }
END { printf "%s", violations }
' "$FILE_PATH")
        ;;
    *.rb)
        # Ruby: count lines between def method_name and end
        VIOLATIONS=$(awk -v limit="$FUNC_LIMIT" '
BEGIN { fname=""; fline=0; body=0; depth=0; violations="" }
/^[[:space:]]*def[[:space:]]+[a-zA-Z_]/ {
    if (fname != "" && body > limit) {
        violations = violations "  Line " fline ": " body " lines (limit: " limit ")\n"
    }
    fname=$0; sub(/^[[:space:]]+/, "", fname); fline=NR; body=0; depth=1; next
}
fname != "" && /^[[:space:]]*(if|unless|case|begin|do|class|module|def|while|until|for)[[:space:]]/ { depth++ }
fname != "" && /^[[:space:]]*end[[:space:]]*$/ {
    depth--
    if (depth <= 0) {
        if (body > limit) {
            violations = violations "  Line " fline ": " body " lines (limit: " limit ")\n"
        }
        fname=""; body=0; depth=0
        next
    }
}
fname != "" && depth > 0 { body++ }
END { printf "%s", violations }
' "$FILE_PATH")
        ;;
    *.py)
        # Python: count lines between def and next line at same/lower indentation
        VIOLATIONS=$(awk -v limit="$FUNC_LIMIT" '
BEGIN { fname=""; fline=0; body=0; findent=-1; violations="" }
/^[[:space:]]*def[[:space:]]+[a-zA-Z_]/ {
    if (fname != "" && body > limit) {
        violations = violations "  Line " fline ": " body " lines (limit: " limit ")\n"
    }
    fname=$0; sub(/^[[:space:]]+/, "", fname); fline=NR; body=0
    findent=0; tmp=$0; gsub(/[^ \t].*/, "", tmp); gsub(/\t/, "    ", tmp); findent=length(tmp)
    next
}
fname != "" {
    if (/^[[:space:]]*$/) { body++; next }
    indent=0; tmp=$0; gsub(/[^ \t].*/, "", tmp); gsub(/\t/, "    ", tmp); indent=length(tmp)
    if (indent <= findent) {
        if (body > limit) {
            violations = violations "  Line " fline ": " body " lines (limit: " limit ")\n"
        }
        fname=""; body=0; findent=-1
        if (/^[[:space:]]*def[[:space:]]+[a-zA-Z_]/) {
            fname=$0; sub(/^[[:space:]]+/, "", fname); fline=NR; body=0
            findent=0; tmp=$0; gsub(/[^ \t].*/, "", tmp); gsub(/\t/, "    ", tmp); findent=length(tmp)
        }
    } else {
        body++
    }
}
END {
    if (fname != "" && body > limit) {
        violations = violations "  Line " fline ": " body " lines (limit: " limit ")\n"
    }
    printf "%s", violations
}
' "$FILE_PATH")
        ;;
    *.go)
        # Go: count lines between func declaration opening { and closing }
        VIOLATIONS=$(awk -v limit="$FUNC_LIMIT" '
BEGIN { fname=""; fline=0; body=0; depth=0; violations="" }
/^[[:space:]]*func[[:space:]]/ {
    fname=$0; sub(/^[[:space:]]+/, "", fname); fline=NR; body=0; depth=0
    if (/{/) { depth++ }
    next
}
fname != "" && /{/ { depth++ }
fname != "" && /}/ {
    depth--
    if (depth <= 0) {
        if (body > limit) {
            violations = violations "  Line " fline ": " body " lines (limit: " limit ")\n"
        }
        fname=""; body=0; depth=0
        next
    }
}
fname != "" && depth > 0 { body++ }
END { printf "%s", violations }
' "$FILE_PATH")
        ;;
esac

if [[ -n "$VIOLATIONS" ]]; then
    echo "" >&2
    echo "WARNING: Function body exceeds $FUNC_LIMIT lines in $FILE_PATH. Shape constraint: functions <= $FUNC_LIMIT lines." >&2
    echo "$VIOLATIONS" >&2
    echo "Consider extracting helper functions or decomposing." >&2
    echo "" >&2
    # Exit 0 = ADVISORY WARNING (does not block, pre-existing violations acknowledged)
    exit 0
fi

exit 0
