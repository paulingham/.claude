#!/usr/bin/env bash
# Bash Write Guard — PreToolUse Bash hook.
#
# Closes the orchestrator-discipline gap: a Write/Edit call to a protected file
# is blocked, but the orchestrator can bypass it by spawning a Bash subprocess
# (`python3 -c "open('settings.json','w')..."`, `sed -i ...`, redirects, etc).
# This hook detects those patterns and blocks them at the Bash boundary.
#
# Mirrors orchestrator-discipline.sh policy:
#   - Calls from inside a worktree (.claude/worktrees/agent-*) are ALLOWED
#     (subagents are trusted to write per rules/agent-protocol.md).
#   - Calls from the orchestrator (PWD = main tree) targeting protected
#     extensions (.json, .sh, .yaml, .yml) are BLOCKED.
#
# Profile=minimal so it ALWAYS runs (matches orchestrator-discipline,
# main-branch-guard, quality-gate).
#
# enforces: rules/core.md:Iron Laws
# protects: build-implementation

source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "PreToolUse:${TOOL_NAME:-Bash}"
trap 'log_hook_event $?' EXIT

set -uo pipefail

source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/hook-profile.sh" && check_hook_profile "minimal" || exit 0

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

[[ "$TOOL_NAME" != "Bash" ]] && exit 0
[[ -z "$COMMAND" ]] && exit 0

is_caller_in_worktree() {
    local toplevel
    toplevel=$(git rev-parse --show-toplevel 2>/dev/null)
    [[ "$toplevel" == *"/.claude/worktrees/agent-"* ]] || [[ "$PWD" == *"/.claude/worktrees/agent-"* ]]
}

is_caller_in_worktree && exit 0

# Pattern detectors — each returns 0 if it matches a write-to-protected-file.
# Protected extensions: .json, .sh, .yaml, .yml.
matches_python_open_write() {
    # python ... open(...) ... '.{ext}' ... 'w'|'a'|'wb'|'ab'
    [[ "$1" =~ open[[:space:]]*\( ]] || return 1
    [[ "$1" =~ \.(json|sh|yaml|yml) ]] || return 1
    [[ "$1" =~ [\'\"](w|a|wb|ab)[\'\"] ]]
}

matches_json_dump() {
    # json.dump(...) anywhere in the command paired with a .json filename.
    [[ "$1" =~ json\.dump ]] && [[ "$1" =~ \.json ]]
}

matches_sed_in_place() {
    # sed -i / --in-place targeting a protected-extension filename.
    [[ "$1" =~ sed[[:space:]]+(-i|--in-place) ]] || return 1
    [[ "$1" =~ \.(json|sh) ]]
}

matches_protected_redirect() {
    # `>` or `>>` immediately writing to settings.json or any *.sh file.
    # The redirect must target a protected path, not /tmp/* etc.
    [[ "$1" =~ \>\>?[[:space:]]*([^[:space:]]*/)?settings\.json([[:space:]]|$|\&) ]] && return 0
    [[ "$1" =~ \>\>?[[:space:]]*([^[:space:]]*/)?[^[:space:]/]+\.sh([[:space:]]|$|\&) ]]
}

is_open_read_only() {
    # open(f), open(f, 'r'), open(f, 'rb') — explicit read shapes that must not
    # block. Returns 0 when command is a read-only open shape; 1 otherwise.
    # Mirrors matches_python_open_write's mode literal set so the two stay in
    # lockstep — any mode in the write set forfeits the read-only guard.
    [[ "$1" =~ open[[:space:]]*\( ]] || return 1
    [[ "$1" =~ [\'\"](w|a|wb|ab)[\'\"] ]] && return 1
    return 0
}

is_write_to_protected() {
    is_open_read_only "$1" && return 1
    matches_python_open_write "$1" && return 0
    matches_json_dump "$1" && return 0
    matches_sed_in_place "$1" && return 0
    matches_protected_redirect "$1" && return 0
    return 1
}

is_write_to_protected "$COMMAND" || exit 0

# Path resolution explicitly excludes /tmp/* destinations: the redirect detector
# anchors on `settings.json` or `.sh` filenames; bare `/tmp/foo.txt` passes
# unaffected because it has no protected extension.

_bwg_redact() {
    printf '%s' "$1" | sed -E 's#(://)[^/@[:space:]]+:[^/@[:space:]]+@#\1REDACTED@#g'
}

_bwg_log_violation() {
    local sid tid dir
    sid="${CLAUDE_SESSION_ID:-local-$$}"
    sid="${sid//[^a-zA-Z0-9_.-]/}"
    tid="${CLAUDE_PIPELINE_TASK_ID:-}"
    dir="$HOME/.claude/metrics/${sid:-local-$$}"
    mkdir -p "$dir" 2>/dev/null || return 0
    jq -nc \
        --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        --arg sid "$sid" \
        --arg tid "$tid" \
        --arg cmd "$(_bwg_redact "$COMMAND")" \
        '{timestamp:$ts,session_id:$sid,task_id:$tid,command:$cmd,source:"prevented",action:"prevented"}' \
        >> "$dir/bash-write-violations.jsonl" 2>/dev/null || true
}

_bwg_log_violation

cat >&2 <<EOF
BLOCKED: Orchestrator Bash bypass detected — writing protected files via Bash is the same violation as using Write/Edit directly. Use /harness-config instead.
Command: $(_bwg_redact "$COMMAND")
EOF
exit 2
