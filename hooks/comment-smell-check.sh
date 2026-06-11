#!/usr/bin/env bash
# Comment Smell Check — PostToolUse hook (runs alongside function-body-check.sh).
# Flags explanatory WHAT comments that restate code, on NEW/changed source lines.
# BLOCKS (exit 2) on a new/changed WHAT comment; advisory (exit 0) on legacy comments.
# Doc-comments, license headers, WHY:/SAFETY: notes, and directive/pragma comments pass.
# Supports: .ts/.tsx/.js/.jsx/.rb/.py/.go
#
# enforces: protocols/engineering-invariants.md:Comments
# protects: build-implementation, code-review

# Hook profile and loop guard
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "PostToolUse:${TOOL_NAME:-Write}"
trap 'log_hook_event $?' EXIT

source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/hook-profile.sh" && check_hook_profile "standard" || exit 0
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/loop-guard.sh" && check_loop_guard "comment-smell-check" || exit 0

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

# ---- New/legacy discrimination (identical algorithm to function-body-check) ----
# Determine the set of ADDED line texts to inspect. Any git error => fail-open advisory.
REPO_ROOT=$(git -C "$(dirname "$FILE_PATH")" rev-parse --show-toplevel 2>/dev/null) || exit 0
[[ -z "$REPO_ROOT" ]] && exit 0

if git -C "$REPO_ROOT" ls-files --error-unmatch -- "$FILE_PATH" >/dev/null 2>&1; then
    # Tracked file: inspect only lines added in the working-tree diff vs HEAD.
    DIFF=$(git -C "$REPO_ROOT" diff HEAD -- "$FILE_PATH" 2>/dev/null) || exit 0
    [[ -z "$DIFF" ]] && exit 0
    ADDED_LINES=$(printf '%s\n' "$DIFF" | grep '^+' | grep -v '^+++' | sed 's/^+//')
else
    # Untracked/new file: every line is new — inspect the whole file.
    ADDED_LINES=$(cat "$FILE_PATH")
fi

[[ -z "$ADDED_LINES" ]] && exit 0

# is_what_comment <line> => prints "1" if the line is a blocking WHAT comment.
# A candidate is a `#` / `//` line comment or a `/* */` block comment. Exemptions
# (doc-comment, license, WHY-prefix, directive/pragma) make it PASS.
is_what_comment() {
    local line="$1"
    local trimmed="${line#"${line%%[![:space:]]*}"}"

    # Candidate must START with a comment marker (full-line comment), not inline trailing.
    case "$trimmed" in
        '#'*|'//'*|'/*'*) ;;
        *) return 1 ;;
    esac

    # --- EXEMPTIONS (any match => pass) ---
    # Shebang.
    case "$trimmed" in '#!'*) return 1 ;; esac
    # Doc-comment markers.
    case "$trimmed" in '/**'*|'///'*) return 1 ;; esac
    # Python docstring lines.
    case "$trimmed" in '"""'*|"'''"*) return 1 ;; esac
    # Legal / license headers.
    if printf '%s' "$trimmed" | grep -qE 'SPDX|Copyright|License|@license'; then
        return 1
    fi
    # WHY-prefixed intent/contract/warning comments (case-insensitive).
    # Includes SSOT-endorsed categories: contract, warning of consequences, rationale.
    if printf '%s' "$trimmed" | grep -qiE '^(#|//)[[:space:]]*(WHY|SAFETY|NOTE|HACK|TODO|FIXME|WARNING|IMPORTANT|XXX|REVIEW|CONTRACT|RETURNS|RAISES|THROWS|PRECONDITION|POSTCONDITION):'; then
        return 1
    fi
    # Doc-comment param/return/type annotations.
    if printf '%s' "$trimmed" | grep -qE '@(param|return|returns|type|license)'; then
        return 1
    fi
    # Directive / pragma comments (frozen literal, rubocop, type, noqa, pylint,
    # eslint, ts-pragmas, prettier/biome ignore, Python encoding, vim modelines).
    if printf '%s' "$trimmed" | grep -qE 'frozen_string_literal:|rubocop:|^#[[:space:]]*type:|noqa|pylint:|eslint-disable|@ts-|prettier-ignore|biome-ignore|^#[[:space:]]*-\*-|^#[[:space:]]*coding:|^#[[:space:]]*vim:|^#[[:space:]]*-!-'; then
        return 1
    fi

    # Only block HIGH-CONFIDENCE narration: a bare prose comment whose first word is
    # a lowercase imperative verb that restates adjacent code. When in doubt, exempt.
    local text
    text="${trimmed#'#'}"
    text="${text#'//'}"
    text="${text#'/*'}"
    text="${text#"${text%%[![:space:]]*}"}"
    if printf '%s' "$text" | grep -qiE '^(increment|loop|iterate|set|get|check|call|return|create|initialize|fetch|update|delete|remove|add|build|send|open|close|read|write|load|save|parse|format|convert|handle|process|compute|calculate|run|start|stop|reset|clear|sort|filter|map|find|count|print|log|show|hide|enable|disable|append|insert|push|pop|shift|unshift)[[:space:]]'; then
        printf '1'
    fi
}

VIOLATION=0
while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    if [[ -n "$(is_what_comment "$line")" ]]; then
        VIOLATION=1
        break
    fi
done <<< "$ADDED_LINES"

if [[ "$VIOLATION" -eq 1 ]]; then
    echo "" >&2
    echo "BLOCKED: comment restates code (WHAT). Delete it or rewrite as WHY (intent/constraint/contract). Doc-comments, license headers, and WHY:/SAFETY: notes are allowed. See protocols/engineering-invariants.md § Comments." >&2
    echo "  File: $FILE_PATH" >&2
    echo "" >&2
    exit 2
fi

exit 0
