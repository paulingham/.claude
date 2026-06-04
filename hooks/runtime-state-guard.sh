#!/usr/bin/env bash
# runtime-state-guard — PreToolUse:Bash + PreToolUse:Write hook.
#
# Denies operations that write runtime state under REPO_ROOT instead of the
# correct HARNESS_DATA location ($CLAUDE_PLUGIN_DATA / $CLAUDE_CONFIG_DIR /
# $HOME/.claude — see hooks/_lib/harness-paths.sh).
#
# Protected operations:
#   Bash tool: mkdir (any form) targeting pipeline-state/ under REPO_ROOT
#   Write tool: file_path targeting <REPO_ROOT>/pipeline-state/...
#
# This directly prevents the contamination class found in the 2026-06-03
# incident (ws-g wrote pipeline-state/ws-g-spec-grounding/ into the repo tree;
# 4 other root pipeline-state dirs similarly created by concurrent sessions).
#
# ENFORCING (exit 2): this hook protects against the exact contamination class
# found; unlike the advisory hooks it IS blocking. The harness convention allows
# new enforcing hooks for clearly-specified, unambiguous violation classes.
#
# Escape hatch: CLAUDE_DISABLE_RUNTIME_STATE_GUARD=1 suppresses all checks.
#
# enforces: CLAUDE.md § Runtime State Location
# protects: root working tree from runtime state contamination
# references: forensics-instinct-injector-edit.md Anomaly 3, Recommendation 5
# see-also: hooks/bash-write-guard.sh (Bash-path-guard precedent)
# if-broken-look-at: $HARNESS_DATA/metrics/{session}/runtime-state-violations.jsonl

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_lib/harness-paths.sh"
# log.sh sourced from deployed location; fails open when not available (e.g. test env)
# shellcheck source=/dev/null
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/log.sh" 2>/dev/null || {
    _log_hook_start() { :; }; _log_hook_trigger() { :; }; log_hook_event() { :; }
}
_log_hook_start
_log_hook_trigger "PreToolUse:Bash+Write"
trap 'log_hook_event $?' EXIT

set -uo pipefail

# Escape hatch (per-session)
[[ "${CLAUDE_DISABLE_RUNTIME_STATE_GUARD:-0}" == "1" ]] && exit 0

INPUT=$(cat)
TOOL_NAME=$(printf '%s' "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)

# Only handle Bash and Write tools
case "$TOOL_NAME" in
    Bash|Write) ;;
    *) exit 0 ;;
esac

# ---------------------------------------------------------------------------
# Determine REPO_ROOT — git toplevel from current directory.
# Canonicalize to resolve symlinks (macOS /var -> /private/var etc).
# If we cannot find a git repo, fail open.
# ---------------------------------------------------------------------------

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
# Canonicalize via cd + pwd -P (pure bash, portable, no realpath needed)
REPO_ROOT=$(cd "$REPO_ROOT" 2>/dev/null && pwd -P) || exit 0

# ---------------------------------------------------------------------------
# Worktree check: if the actual CWD is inside a worktree, allow everything.
# Mirrors is_caller_in_worktree from bash-write-guard.sh.
#
# SECURITY: early-allow requires the *canonicalized CWD* to be inside the
# worktree path — never on the env var value alone. A worktree-session agent
# running at REPO_ROOT always has CLAUDE_WORKTREE_PATH set to a valid worktree
# path, so an env-var-only check would bypass this enforcing guard entirely
# (the exact 2026-06-03 incident pattern).
# ---------------------------------------------------------------------------

_rsg_is_worktree() {
    # Canonicalize the actual CWD first (resolve macOS /var -> /private/var).
    local canon_pwd
    canon_pwd=$(pwd -P 2>/dev/null) || return 1

    # Fast path: CWD is already inside a worktree directory tree.
    [[ "$canon_pwd" == *"/.claude/worktrees/agent-"* ]] && return 0

    # If REPO_ROOT itself is a worktree path the entire session is worktree-scoped.
    # REPO_ROOT is already canonicalized (via cd + pwd -P above).
    [[ "$REPO_ROOT" == *"/.claude/worktrees/agent-"* ]] && return 0

    # If CLAUDE_WORKTREE_PATH is set, verify that the canon CWD is actually
    # inside the canonicalized worktree path — not just that the env var looks
    # like a worktree path. This prevents bypass when the var is set but the
    # agent is operating at REPO_ROOT.
    if [[ -n "${CLAUDE_WORKTREE_PATH:-}" && \
          "${CLAUDE_WORKTREE_PATH}" == *"/.claude/worktrees/agent-"* ]]; then
        local canon_wt
        canon_wt=$(cd "${CLAUDE_WORKTREE_PATH}" 2>/dev/null && pwd -P) || return 1
        [[ "$canon_pwd" == "$canon_wt" || "$canon_pwd" == "$canon_wt/"* ]] && return 0
    fi

    return 1
}

# ---------------------------------------------------------------------------
# Helper: does the target path resolve under REPO_ROOT/pipeline-state/?
# Canonicalizes the parent directory to handle symlinks (macOS /var -> /private/var).
# ---------------------------------------------------------------------------

_rsg_is_repo_pipeline_state_path() {
    local raw_path="$1"
    local resolved canon_parent canon_resolved

    # Strip leading ./
    raw_path="${raw_path#./}"

    # Build absolute path
    if [[ "$raw_path" == /* ]]; then
        resolved="$raw_path"
    else
        resolved="$REPO_ROOT/$raw_path"
    fi

    # Normalize double-slashes
    resolved="${resolved//\/\///}"

    # Quick prefix match (may fail on macOS symlinks — see canonicalization below)
    if [[ "$resolved" == "${REPO_ROOT}/pipeline-state" ]] || \
       [[ "$resolved" == "${REPO_ROOT}/pipeline-state/"* ]]; then
        return 0
    fi

    # Canonicalize: resolve the parent directory (file may not exist yet)
    # Walk up until we find an existing ancestor to canonicalize
    local check="$resolved"
    while [[ "$check" != "/" && ! -d "$check" && ! -f "$check" ]]; do
        check="${check%/*}"
    done
    if [[ -d "$check" || -f "$check" ]]; then
        local canon_check
        canon_check=$(cd "$(dirname "$check")" 2>/dev/null && pwd -P) || return 1
        canon_resolved="${canon_check}/$(basename "$check")"
        # Reattach the suffix that was trimmed
        local suffix="${resolved#$check}"
        canon_resolved="${canon_resolved}${suffix}"
        if [[ "$canon_resolved" == "${REPO_ROOT}/pipeline-state" ]] || \
           [[ "$canon_resolved" == "${REPO_ROOT}/pipeline-state/"* ]]; then
            return 0
        fi
    fi

    return 1
}

# ---------------------------------------------------------------------------
# Bash tool: detect mkdir targeting pipeline-state under REPO_ROOT.
# Also handles absolute paths by checking if any argument resolves under
# REPO_ROOT/pipeline-state via _rsg_is_repo_pipeline_state_path.
# ---------------------------------------------------------------------------

_rsg_mkdir_targets_pipeline_state() {
    local cmd="$1"
    # Relative / ./-prefixed pipeline-state paths
    if [[ "$cmd" =~ (^|[[:space:]])(\.?/?)pipeline-state(/[^[:space:]]*)?([[:space:]]|$) ]]; then
        return 0
    fi
    # Absolute path containing /pipeline-state/ — extract and verify under REPO_ROOT
    # Scan words in the command that look like absolute paths with pipeline-state.
    # set -f/+f disables glob expansion so $cmd words are not expanded by the shell.
    local word
    set -f
    for word in $cmd; do
        if [[ "$word" == *"/pipeline-state"* && "$word" == /* ]]; then
            set +f
            _rsg_is_repo_pipeline_state_path "$word" && return 0
            set -f
        fi
    done
    set +f
    return 1
}

# ---------------------------------------------------------------------------
# Logging and block
# ---------------------------------------------------------------------------

_rsg_log_violation() {
    local tool="$1"
    local target="$2"
    local sid="${CLAUDE_SESSION_ID:-local-$$}"
    sid="${sid//[^a-zA-Z0-9_.-]/}"
    local dir="$HARNESS_DATA/metrics/${sid}"
    mkdir -p "$dir" 2>/dev/null || return 0
    jq -nc \
        --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        --arg sid "$sid" \
        --arg tool "$tool" \
        --arg target "$target" \
        --arg repo "$REPO_ROOT" \
        '{timestamp:$ts,session_id:$sid,tool:$tool,target:$target,repo_root:$repo,action:"blocked"}' \
        >> "$dir/runtime-state-violations.jsonl" 2>/dev/null || true
}

_rsg_block() {
    local tool="$1"
    local target="$2"
    _rsg_log_violation "$tool" "$target"
    cat >&2 <<EOF
BLOCKED [runtime-state-guard]: Runtime state written under REPO_ROOT.
  Tool            : $tool
  Target          : $target
  Repo root       : $REPO_ROOT
  Violation       : pipeline-state/ must NOT be created under the repo root working tree.
  Correct location: \$CLAUDE_PLUGIN_DATA (HARNESS_DATA) — see hooks/_lib/harness-paths.sh
                    and CLAUDE.md § Runtime State Location.
  Reference       : forensics-instinct-injector-edit.md Anomaly 3 / Recommendation 5
EOF
    exit 2
}

# ---------------------------------------------------------------------------
# Main dispatch
# ---------------------------------------------------------------------------

_rsg_is_worktree && exit 0

if [[ "$TOOL_NAME" == "Bash" ]]; then
    COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)
    [[ -z "$COMMAND" ]] && exit 0

    # Must be a mkdir invocation
    if [[ "$COMMAND" =~ (^|[[:space:]])mkdir([[:space:]]|$) ]]; then
        if _rsg_mkdir_targets_pipeline_state "$COMMAND"; then
            # Safe path exceptions: /tmp or /var (not repo-rooted)
            if [[ "$COMMAND" =~ /tmp/pipeline-state ]] || \
               [[ "$COMMAND" =~ /var/pipeline-state ]]; then
                exit 0
            fi
            _rsg_block "Bash" "$COMMAND"
        fi
    fi
    exit 0
fi

if [[ "$TOOL_NAME" == "Write" ]]; then
    FILE_PATH=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
    [[ -z "$FILE_PATH" ]] && exit 0

    if _rsg_is_repo_pipeline_state_path "$FILE_PATH"; then
        _rsg_block "Write" "$FILE_PATH"
    fi
    exit 0
fi

exit 0
