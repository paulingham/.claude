#!/usr/bin/env bash
# Syntax Check — PostToolUse BLOCKING syntax gate
# Fires after Write/Edit. Runs a syntax-only parse (no execution, no network,
# no build/module resolution) of the file just written/edited and HARD BLOCKS
# (exit 2) syntactically-invalid code before it lands.
#
# Inspired by SWE-agent ACI (arXiv:2405.15793): fail fast on un-parseable code
# so engineers never burn tokens debugging code that never parsed.
#
# Supports: .py .rb .go .ts .tsx .js .jsx .sh .json
# A missing toolchain NEVER blocks — each parser SKIPs (exit 0) when its tool
# is absent, so degraded environments stay unblocked.
#
# Env hatches (session-level reversibility escapes):
#   CLAUDE_SYNTAX_CHECK=0|off          — disable the gate entirely (any case)
#   CLAUDE_SYNTAX_CHECK_SKIP_LANGS=... — comma-separated tokens to skip
#                                        (tokens: py rb go ts js sh json)
#
# enforces: rules/core.md discipline
# protects: build-implementation, code-review

# Hook profile and loop guard
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "PostToolUse:${TOOL_NAME:-Write}"
trap 'log_hook_event $?' EXIT

source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/hook-profile.sh" && check_hook_profile "standard" || exit 0
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/loop-guard.sh" && check_loop_guard "syntax-check" || exit 0

# Global hatch — cheap short-circuit before reading stdin.
SYNTAX_FLAG=$(printf '%s' "${CLAUDE_SYNTAX_CHECK:-}" | tr '[:upper:]' '[:lower:]')
if [[ "$SYNTAX_FLAG" == "0" || "$SYNTAX_FLAG" == "off" ]]; then
    exit 0
fi

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# Only check if we have a file path
if [[ -z "$FILE_PATH" ]]; then
    exit 0
fi

# Only handle parseable source/config extensions.
# NOTE: unlike cc-check.sh / code-shape-check.sh, we intentionally do NOT skip
# test files — invalid test syntax must also be caught before it lands.
case "$FILE_PATH" in
    *.py|*.rb|*.go|*.ts|*.tsx|*.js|*.jsx|*.sh|*.json) ;;
    *) exit 0 ;;
esac

# Skip if file doesn't exist (deleted)
if [[ ! -f "$FILE_PATH" ]]; then
    exit 0
fi

# Map a file path's extension to a canonical language token.
# .ts/.tsx -> ts, .js/.jsx -> js; others map 1:1.
lang_token() {
    case "$1" in
        *.py)   echo "py" ;;
        *.rb)   echo "rb" ;;
        *.go)   echo "go" ;;
        *.ts|*.tsx) echo "ts" ;;
        *.js|*.jsx) echo "js" ;;
        *.sh)   echo "sh" ;;
        *.json) echo "json" ;;
    esac
}

LANG=$(lang_token "$FILE_PATH")

# Per-language opt-out: comma-separated tokens in CLAUDE_SYNTAX_CHECK_SKIP_LANGS.
if [[ -n "${CLAUDE_SYNTAX_CHECK_SKIP_LANGS:-}" ]]; then
    case ",${CLAUDE_SYNTAX_CHECK_SKIP_LANGS}," in
        *",${LANG},"*) exit 0 ;;
    esac
fi

# Syntax-only parse for a TypeScript/JavaScript file.
# Prefer a LOCAL tsc (covers both TS and JS via --allowJs). If no local tsc:
#   .js/.jsx -> node --check;  .ts/.tsx -> SKIP (node cannot parse TS).
# Echoes parser stderr on failure; returns the parser's exit status.
parse_ts_js() {
    if command -v npx &> /dev/null && npx --no-install tsc --version &> /dev/null; then
        npx --no-install tsc --noEmit --allowJs "$FILE_PATH" 2>&1
        return $?
    fi
    case "$FILE_PATH" in
        *.js|*.jsx)
            command -v node &> /dev/null || return 0
            node --check "$FILE_PATH" 2>&1
            return $?
            ;;
        *) return 0 ;;  # .ts/.tsx with no local tsc -> skip
    esac
}

# Dispatch to the syntax-only parser for the file's language.
# Each parser is guarded by command -v and returns 0 (SKIP) if its tool is
# absent. Echoes captured parser stderr on failure; returns parser exit status.
parse_check() {
    case "$LANG" in
        py)   command -v python3 &> /dev/null || return 0; python3 -m py_compile "$FILE_PATH" 2>&1; return $? ;;
        rb)   command -v ruby &> /dev/null || return 0; ruby -c "$FILE_PATH" 2>&1; return $? ;;
        go)   command -v gofmt &> /dev/null || return 0; gofmt -e "$FILE_PATH" > /dev/null 2>&1; return $? ;;
        ts|js) parse_ts_js ;;
        sh)   command -v bash &> /dev/null || return 0; bash -n "$FILE_PATH" 2>&1; return $? ;;
        json) command -v jq &> /dev/null || return 0; jq empty "$FILE_PATH" 2>&1; return $? ;;
        *) return 0 ;;
    esac
}

PARSER_STDERR=$(parse_check)
PARSER_STATUS=$?

if [[ "$PARSER_STATUS" -ne 0 ]]; then
    echo "" >&2
    echo "$FILE_PATH" >&2
    echo "SYNTAX ERROR — blocked before it lands" >&2
    echo "$PARSER_STDERR" >&2
    echo "" >&2
    echo "Bypass: CLAUDE_SYNTAX_CHECK=0 (session) or CLAUDE_SYNTAX_CHECK_SKIP_LANGS=$LANG (this language)." >&2
    echo "" >&2
    exit 2
fi

exit 0
