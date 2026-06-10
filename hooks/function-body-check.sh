#!/usr/bin/env bash
# Function Body Length Check — PostToolUse hook (runs alongside code-shape-check.sh)
# Checks source files for function bodies exceeding the line limit.
# Uses language-specific heuristics to detect function boundaries.
# Supports: .ts/.tsx/.js/.jsx/.rb/.py/.go
# Per-language smell limits: Ruby 5, TS/JS 12, Python/Go 8.
# BLOCKS (exit 2) on a new/changed function over the limit; ADVISORY (exit 0) on
# pre-existing legacy violations. New vs legacy is decided by diffing the file
# against HEAD; any git failure fails open to advisory.
#
# enforces: rules/core.md:Code Shape Limits
# protects: build-implementation, code-review

# Hook profile and loop guard
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "PostToolUse:${TOOL_NAME:-Write}"
trap 'log_hook_event $?' EXIT

source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/hook-profile.sh" && check_hook_profile "standard" || exit 0
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/loop-guard.sh" && check_loop_guard "function-body-check" || exit 0

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

# Per-language smell limit: Ruby is tightest (5), TS/JS more permissive (12),
# Python/Go keep the historical 8-line fallback. Resolved before the awk parsers
# so each language is measured against its own cap.
case "$FILE_PATH" in
    *.rb)
        FUNC_LIMIT="${CLAUDE_FUNCTION_LINE_LIMIT_RB:-5}" ;;
    *.ts|*.tsx|*.js|*.jsx)
        FUNC_LIMIT="${CLAUDE_FUNCTION_LINE_LIMIT_TS:-12}" ;;
    *)
        FUNC_LIMIT="${CLAUDE_FUNCTION_LINE_LIMIT:-8}" ;;
esac

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

if [[ -z "$VIOLATIONS" ]]; then
    exit 0
fi

# Emit the advisory warning body shared by both the block and advisory paths.
print_violation_warning() {
    echo "" >&2
    echo "WARNING: Function body exceeds $FUNC_LIMIT lines in $FILE_PATH. Shape constraint: functions <= $FUNC_LIMIT lines." >&2
    echo "$VIOLATIONS" >&2
    echo "Consider extracting helper functions or decomposing." >&2
    echo "" >&2
}

# WHY: PostToolUse fires after the write, so the file is on disk and can be
# diffed against HEAD to separate new/changed violations (block) from
# pre-existing legacy ones (advisory). Any git failure fails open to advisory.
REPO_ROOT=$(git -C "$(dirname "$FILE_PATH")" rev-parse --show-toplevel 2>/dev/null)
if [[ -z "$REPO_ROOT" ]]; then
    print_violation_warning
    exit 0
fi

# Changed-line ranges from the unified diff's "@@ -x,y +N,M @@" hunk headers,
# one "start end" pair per line. Empty when the file is untracked or unchanged.
changed_line_ranges() {
    local diff="$1"
    echo "$diff" | awk '
/^@@ / {
    h=$0; sub(/^@@ -[0-9,]+ \+/, "", h); sub(/ @@.*/, "", h)
    n=h; m=1
    if (index(h, ",") > 0) { split(h, a, ","); n=a[1]; m=a[2] }
    if (m > 0) print n, n + m - 1
}'
}

# True when a violation line falls inside any changed hunk range.
fline_in_ranges() {
    local fline="$1" ranges="$2" start end
    while read -r start end; do
        [[ -z "$start" ]] && continue
        if (( fline >= start && fline <= end )); then return 0; fi
    done <<< "$ranges"
    return 1
}

BLOCKING=0
if ! git -C "$REPO_ROOT" ls-files --error-unmatch "$FILE_PATH" >/dev/null 2>&1; then
    # Untracked/new file: every violation is new code → block.
    BLOCKING=1
else
    DIFF=$(git -C "$REPO_ROOT" diff HEAD -- "$FILE_PATH" 2>/dev/null)
    if [[ -n "$DIFF" ]]; then
        RANGES=$(changed_line_ranges "$DIFF")
        while IFS= read -r line; do
            [[ "$line" =~ Line\ ([0-9]+): ]] || continue
            if fline_in_ranges "${BASH_REMATCH[1]}" "$RANGES"; then
                BLOCKING=1
                break
            fi
        done <<< "$VIOLATIONS"
    fi
    # Empty DIFF → no tracked changes → all violations legacy → advisory.
fi

print_violation_warning
if (( BLOCKING )); then
    echo "BLOCKED: new/changed function exceeds the per-language limit (Ruby 5 / TS 12). Split it, or if the pieces would be entangled, keep them together — see protocols/engineering-invariants.md § Code Shape." >&2
    exit 2
fi

exit 0
