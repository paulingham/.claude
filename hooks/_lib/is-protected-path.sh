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
#             When relpath was re-derived via --show-prefix (macOS alias or symlinked
#             ancestor), Step 4 also uses the canonical repo-relative path to probe
#             siblings — preventing a fail-open via symlink ancestor net-new writes.
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
    # `dirname --` terminates option parsing so leading-dash paths (e.g. -README.md)
    # are not treated as flags.  Fail-closed on dirname error or empty result.
    parent="$(dirname -- "$path" 2>/dev/null)" || return 0
    [[ -z "$parent" ]] && return 0
    repo="$(git -C "$parent" rev-parse --show-toplevel 2>/dev/null)"
    rc=$?
    # git returned error (128 = not a repo), or repo is empty → BLOCK
    [[ $rc -ne 0 || -z "$repo" ]] && return 0

    # Step 3: is the target itself a tracked file? → BLOCK
    relpath="${path#"$repo"/}"
    # Symlink divergence guard: when relpath is still absolute after stripping
    # the repo prefix, the path's textual location does not start with $repo.
    # This can happen in two distinct cases:
    #   (a) macOS /var → /private/var aliasing: $path uses /var, git returns
    #       /private/var for $repo — same filesystem location, different strings.
    #       Here $parent (from dirname of $path) also shares the /var prefix, so
    #       we can re-resolve the repo using $parent and strip from there.
    #   (b) Symlink exploit: $parent is a symlink OUTSIDE the repo that points
    #       INTO the repo. git follows the link and returns $repo. But $path
    #       (= "$parent/filename") is not under $repo as a string. Fail-closed.
    # Distinguish: try to re-strip using $parent as the repo prefix anchor.
    # $path is always "$parent/<name>" by construction (dirname inverse), so if
    # the repo root is the ancestor of $parent (textually), the strip will work.
    # _relpath_via_prefix is set when relpath is re-derived via --show-prefix.
    # Covers two cases: (a) macOS /var→/private/var aliasing and (b) symlinked
    # ancestor (where $parent is a real dir reached via a symlink higher up).
    # When set, Step 4 uses dirname(relpath) for parent_rel so the sibling probe
    # uses the canonical repo-relative path rather than the textually-diverged $parent.
    local _relpath_via_prefix=0
    if [[ "$relpath" == /* ]]; then
        # relpath is still absolute: the path's textual prefix does not match
        # $repo.  Two cases:
        #   (a) macOS /var → /private/var aliasing: $path uses /var prefix; git
        #       resolved /private/var for $repo.  $parent is a REAL directory
        #       (not itself a symlink) — [[ -L "$parent" ]] is false.
        #   (b) Symlink exploit: $parent is a symlink directory placed OUTSIDE the
        #       repo whose target points INSIDE the repo.  [[ -L "$parent" ]] is true.
        # Distinguish: if $parent is a symlink, fail-closed (block the exploit).
        # If $parent is a real directory, it's the macOS alias case — re-derive
        # relpath via git --show-prefix which follows the same OS resolution.
        if [[ -L "$parent" ]]; then
            # $parent is a symlink — could be the from-outside-into-repo exploit.
            # Fail-closed.
            return 0
        fi
        # Case (a): re-derive relpath via git --show-prefix from $parent.
        # show-prefix returns "subdir/" (with trailing slash) or "" (at root).
        local _prefix=""
        _prefix="$(git -C "$parent" rev-parse --show-prefix 2>/dev/null)"
        relpath="${_prefix}${path##*/}"
        # If relpath is still absolute after this (should be impossible), block.
        [[ "$relpath" == /* ]] && return 0
        _relpath_via_prefix=1
    fi
    if git -C "$repo" ls-files --error-unmatch -- "$relpath" >/dev/null 2>&1; then
        return 0
    fi

    # Step 4: target is untracked — probe the parent directory for tracked
    # siblings. If any exist, this is a tracked-directory net-new write → BLOCK.
    # When relpath was re-derived via --show-prefix (macOS alias or symlinked
    # ancestor), derive parent_rel from relpath so the sibling probe uses the
    # canonical repo-relative path rather than the symlink-diverged $parent.
    if [[ $_relpath_via_prefix -eq 1 ]]; then
        parent_rel="$(dirname -- "$relpath")"
    else
        parent_rel="${parent#"$repo"/}"
        [[ "$parent" == "$repo" ]] && parent_rel="."
    fi
    # capture THEN test (pipefail-safe — avoids the subshell-pipefail trap)
    tracked="$(git -C "$repo" ls-files -- "$parent_rel/" 2>/dev/null | head -1)"
    [[ -n "$tracked" ]] && return 0

    # Genuine scratch directory with no tracked files → ALLOW
    return 1
}
