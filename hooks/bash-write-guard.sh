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
#     (subagents are trusted to write per protocols/agent-protocol.md).
#   - Calls from the orchestrator (PWD = main tree) targeting protected
#     extensions (.json, .sh, .yaml, .yml) are BLOCKED.
#
# Profile=minimal so it ALWAYS runs (matches orchestrator-discipline,
# main-branch-guard, quality-gate).
#
# enforces: rules/core.md:Iron Laws
# protects: build-implementation

# Resolve this hook's own directory FIRST so library sourcing is anchored to
# the install that shipped the hook — not to the CLAUDE_PLUGIN_ROOT env chain,
# which may be unset (e.g. worktree-isolated test runs) and otherwise resolve
# to a $HOME/.claude that lacks these libs. A security guard must never fail
# OPEN because an env var was absent: if the profile lib cannot be sourced the
# detectors never run and protected Bash writes slip through. Anchoring on
# BASH_SOURCE keeps the guard fail-safe regardless of caller environment.
_BWG_HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=/dev/null
source "$_BWG_HOOK_DIR/_lib/harness-paths.sh"
source "$_BWG_HOOK_DIR/_lib/log.sh"
# is_protected_path: block-by-protected-location helper (consults git index)
source "$_BWG_HOOK_DIR/_lib/is-protected-path.sh"
_log_hook_start
_log_hook_trigger "PreToolUse:${TOOL_NAME:-Bash}"
trap 'log_hook_event $?' EXIT

set -uo pipefail

source "$_BWG_HOOK_DIR/hook-profile.sh" && check_hook_profile "minimal" || exit 0

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

[[ "$TOOL_NAME" != "Bash" ]] && exit 0
[[ -z "$COMMAND" ]] && exit 0

is_caller_in_worktree() {
    local toplevel
    # Honor explicit CLAUDE_WORKTREE_PATH first — the orchestrator/spawn-prompt
    # may set this when the agent's PWD has drifted outside the worktree
    # (e.g. between Bash calls that target $HARNESS_DATA/learning/...).
    [[ -n "${CLAUDE_WORKTREE_PATH:-}" && "$CLAUDE_WORKTREE_PATH" == *"/.claude/worktrees/agent-"* ]] && return 0
    toplevel=$(git rev-parse --show-toplevel 2>/dev/null)
    [[ "$toplevel" == *"/.claude/worktrees/agent-"* ]] || [[ "$PWD" == *"/.claude/worktrees/agent-"* ]]
}

is_caller_in_worktree && exit 0

# Append-only writes to learning/**/*.jsonl are observation/instinct captures
# from agents whose PWD has reset off the worktree. They are never overwriting,
# only appending one JSONL line per call. Whitelist them here so agents don't
# need to fight the guard with os.open(..., O_APPEND) constants.
is_learning_jsonl_append() {
    [[ "$1" =~ /learning/[^[:space:]\'\"]*\.jsonl ]] || return 1
    # Append shapes: `>> path.jsonl`, Python open(..., 'a'/'ab'),
    # os.open(..., O_APPEND) constants, or `tee -a`.
    [[ "$1" =~ \>\>[[:space:]] ]] && return 0
    [[ "$1" =~ open[[:space:]]*\([^\)]*[\'\"](a|ab)[\'\"] ]] && return 0
    [[ "$1" =~ O_APPEND ]] && return 0
    [[ "$1" =~ tee[[:space:]]+(-a|--append) ]] && return 0
    return 1
}

is_learning_jsonl_append "$COMMAND" && exit 0

# Freshness-gate evidence writes are orchestrator-state, not source. Mirror
# is_learning_jsonl_append's shape: detect a path-pattern bypass for
# pipeline-state/*/verification-evidence.json (regular + workstream layouts).
# Iron Law 6: orchestrator must be able to refresh a stale stub in-cycle.
is_evidence_json_write() {
    [[ "$1" =~ /pipeline-state/[^[:space:]\'\"]*/verification-evidence\.json([[:space:]\'\"]|$) ]]
}

is_evidence_json_write "$COMMAND" && exit 0

# Pattern detectors — each returns 0 if it matches a write-to-protected-file.
# Protected extensions: .json, .sh, .yaml, .yml. The trailing class
# `([^a-zA-Z0-9]|$)` prevents `.json` from matching as a substring of `.jsonl`,
# `.shrc`, `.yamlfile`, etc.
matches_python_open_write() {
    # python ... open(...) ... '.{ext}' ... 'w'|'a'|'wb'|'ab'
    [[ "$1" =~ open[[:space:]]*\( ]] || return 1
    [[ "$1" =~ \.(json|sh|yaml|yml)([^a-zA-Z0-9]|$) ]] || return 1
    [[ "$1" =~ [\'\"](w|a|wb|ab)[\'\"] ]]
}

matches_json_dump() {
    # json.dump(...) anywhere in the command paired with a .json filename.
    [[ "$1" =~ json\.dump ]] && [[ "$1" =~ \.json([^a-zA-Z0-9]|$) ]]
}

matches_sed_in_place() {
    # sed -i / --in-place targeting a protected-extension filename.
    [[ "$1" =~ sed[[:space:]]+(-i|--in-place) ]] || return 1
    [[ "$1" =~ \.(json|sh)([^a-zA-Z0-9]|$) ]]
}

matches_protected_redirect() {
    # `>` or `>>` immediately writing to settings.json or any *.sh file.
    # The redirect must target a protected path, not /tmp/* etc.
    [[ "$1" =~ \>\>?[[:space:]]*([^[:space:]]*/)?settings\.json([[:space:]]|$|\&) ]] && return 0
    [[ "$1" =~ \>\>?[[:space:]]*([^[:space:]]*/)?[^[:space:]/]+\.sh([[:space:]]|$|\&) ]] && return 0
    # .md (Hole 3): extract every redirect DESTINATION that ends in .md and
    # delegate each to is_protected_path (git-index based decision).
    # FIX: grep the token IMMEDIATELY AFTER the redirect operator (>/>>) only,
    # not the first .md anywhere in the command string.  A source file that
    # appears before the > (e.g. `cat src.md > tracked.md`) must NOT be checked.
    # Strategy: extract each ">> token" or "> token" match, then strip the
    # leading >> or > and whitespace to isolate the destination path.
    if [[ "$1" =~ \>\>?[[:space:]]*([^[:space:]]*/)?[^[:space:]]+\.md([[:space:]]|$|\&) ]]; then
        local _dest="" _match=""
        while IFS= read -r _match; do
            # Strip the leading > or >> (and any trailing spaces) to get the path.
            _dest="${_match#>>}"
            _dest="${_dest#>}"
            _dest="${_dest#"${_dest%%[! ]*}"}"   # strip leading spaces
            # Strip any trailing whitespace or & that the regex included.
            _dest="${_dest%%[[:space:]]*}"
            _dest="${_dest%%&*}"
            [[ -z "$_dest" ]] && continue
            is_protected_path "$_dest" && return 0
        done < <(grep -oE '>>[[:space:]]*[^[:space:]]+\.md([[:space:]]|$)|>[^>][[:space:]]*[^[:space:]]+\.md([[:space:]]|$)' <<<"$1")
    fi
    return 1
}

matches_python_pathlib_write() {
    # Hole 2: Path(...).write_text(t) / write_bytes(t) are invisible to the
    # `open(` keyed detector. Block when a write_text/write_bytes call appears
    # alongside a protected-extension path. The learning-jsonl and evidence
    # whitelists run earlier (caller order), so allowed targets never reach here.
    [[ "$1" =~ write_text[[:space:]]*\( || "$1" =~ write_bytes[[:space:]]*\( ]] || return 1
    [[ "$1" =~ \.(json|sh|yaml|yml)([^a-zA-Z0-9]|$) ]] && return 0
    # .md: check-every-token strategy (mirrors matches_protected_redirect fix).
    # Extracting only the first .md token is a fail-open: a benign source token
    # appearing before the write-target (e.g. a pipeline-state path passed to
    # read_text()) causes the guard to ALLOW without ever inspecting the destination.
    # Safe direction: loop over ALL .md tokens; block if ANY is protected.
    # /tmp/ tokens are explicitly skipped (mirroring _bwg_destination_is_protected).
    if [[ "$1" =~ \.md([^a-zA-Z0-9]|$) ]]; then
        local _md_token=""
        while IFS= read -r _md_token; do
            [[ -z "$_md_token" ]] && continue
            # Strip any surrounding quote characters that grep may have included.
            _md_token="${_md_token//\'/}"
            _md_token="${_md_token//\"/}"
            # /tmp/ paths are scratch; skip rather than delegating to is_protected_path
            # (git fails on /tmp → fail-closed would over-block legitimate scratch writes).
            [[ "$_md_token" == /tmp/* ]] && continue
            is_protected_path "$_md_token" && return 0
        done < <(grep -oE "['\"]?[^'\"[:space:]]+\.md['\"]?" <<<"$1")
    fi
    return 1
}

matches_cp_mv_to_protected() {
    # Hole 1: `cp $WT/$f $f` / `mv ...` copied protected files into the main
    # tree unblocked. cp/mv destination is, by convention, the LAST argument;
    # we decide on that token. Heuristic limitation (fail-closed-ish): we do not
    # parse `-t DIR` / `--target-directory` GNU forms, and a trailing flag would
    # be misread as the dest — both are rare in orchestrator usage. If the final
    # token bears a protected extension and is NOT under /tmp/ and NOT inside a
    # worktree, block. /tmp and worktree destinations are legitimate (scratch
    # output / agent-trusted writes) and pass.
    [[ "$1" =~ (^|[[:space:]])(cp|mv)[[:space:]] ]] || return 1
    _bwg_destination_is_protected "$1"
}

_bwg_destination_is_protected() {
    # The destination is the last whitespace-separated token of a cp/mv command.
    local dest=""
    dest="${1##* }"
    [[ "$dest" == /tmp/* || "$dest" == *"/.claude/worktrees/"* ]] && return 1
    [[ "$dest" =~ \.(json|sh|yaml|yml)([^a-zA-Z0-9]|$) ]] && return 0
    # .md: delegate to is_protected_path (git-index based decision).
    [[ "$dest" =~ \.md([^a-zA-Z0-9]|$) ]] && is_protected_path "$dest" && return 0
    return 1
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
    # cp/mv and write_text/write_bytes are checked BEFORE the open-read-only
    # short-circuit: that guard only governs the `open(` family. A command like
    # `cp x.json y.json` contains no `open(`, so is_open_read_only would return
    # 1 (read-only) and wrongly suppress these detectors if ordered after it.
    matches_cp_mv_to_protected "$1" && return 0
    matches_python_pathlib_write "$1" && return 0
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
    dir="$HARNESS_DATA/metrics/${sid:-local-$$}"
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
