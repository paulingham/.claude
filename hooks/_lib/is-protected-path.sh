#!/usr/bin/env bash
# is-protected-path.sh — Protected-location predicate for write-guard hooks.
#
# Exposes: is_protected_path <abs-path>
#   exit 0 = BLOCK (orchestrator must not write here)
#   exit 1 = ALLOW (genuine scratch / orchestrator-state)
#
# Fail-closed: any git error or missing parent → exit 0 (BLOCK).
#
# Decision precedence:
#   Step 1 — explicit allowlist substrings/regexes → ALLOW immediately
#   Step 2 — resolve repo from the target's parent directory
#             (NOT realpath — macOS lacks --canonicalize-missing on older versions)
#   Step 3 — if target is git-tracked → BLOCK
#   Step 4 — if target is untracked but its parent dir contains tracked siblings → BLOCK
#             (blocks net-new source files such as agents/new.md, hooks/new.sh)
#   fallback → ALLOW (genuine scratch directory with no tracked files)
#
# Known residual: the /pipeline-state/ check is a simple substring match.
# This is acceptable in harness context because no real source file lives
# under a path containing the literal string "/pipeline-state/".
#
# Breadcrumb: if a net-new source file ever slips to main, inspect Step 3
# (ls-files --error-unmatch) and Step 4 (ls-files parent probe) here AND
# the bash-write-guard.sh detector's path-token extraction logic.
#
# Source guard — safe to source multiple times (e.g. bash-write-guard.sh
# sources this, which itself runs under set -uo pipefail):
[[ -n "${_IS_PROTECTED_PATH_LOADED:-}" ]] && return
_IS_PROTECTED_PATH_LOADED=1

is_protected_path() {
    local path="${1:-}"
    local parent="" repo="" relpath="" parent_rel="" rc=0 tracked=""

    # Fail-closed: empty path → BLOCK
    [[ -z "$path" ]] && return 0

    # Step 1: explicit orchestrator-state allowlist → ALLOW immediately
    # /pipeline-state/ is a substring match (acceptable — see header note)
    [[ "$path" == *"/pipeline-state/"* ]] && return 1
    # learning/**/*.jsonl — observation/instinct captures
    [[ "$path" =~ /learning/.*\.jsonl$ ]] && return 1
    # Worktree agent paths — trusted subagent territory
    [[ "$path" == *"/.claude/worktrees/agent-"* ]] && return 1

    # Step 2: resolve the repo toplevel from the target's PARENT directory.
    # Using the parent rather than the target itself handles the case where
    # the target is a net-new file that does not exist yet.
    parent="$(dirname "$path")"
    repo="$(git -C "$parent" rev-parse --show-toplevel 2>/dev/null)"
    rc=$?
    # git returned error (128 = not a repo), or repo is empty → BLOCK
    [[ $rc -ne 0 || -z "$repo" ]] && return 0

    # Step 3: is the target itself a tracked file? → BLOCK
    relpath="${path#"$repo"/}"
    if git -C "$repo" ls-files --error-unmatch -- "$relpath" >/dev/null 2>&1; then
        return 0
    fi

    # Step 4: target is untracked — probe the parent directory for tracked
    # siblings. If any exist, this is a tracked-directory net-new write → BLOCK.
    # capture THEN test (pipefail-safe — avoids the subshell-pipefail trap)
    parent_rel="${parent#"$repo"/}"
    [[ "$parent" == "$repo" ]] && parent_rel="."
    tracked="$(git -C "$repo" ls-files -- "$parent_rel/" 2>/dev/null | head -1)"
    [[ -n "$tracked" ]] && return 0

    # Genuine scratch directory with no tracked files → ALLOW
    return 1
}
