#!/usr/bin/env bash
# Harness-ref resolution: pin the inner pipeline's skills/hooks/rules to a
# specific ~/.claude SHA via a throwaway git worktree, OR default to live $HOME.
# See skills/internal-eval/run/ISOLATION.md and plan validation B2.

# resolve_harness_sha <maybe-sha>   -- empty input means "live".
resolve_harness_sha() {
  [ -z "$1" ] && { echo "live"; return; }
  echo "$1"
}

# resolve_harness_root <maybe-sha> <target-worktree-path>
# Empty sha → $HOME (live). Non-empty sha → create worktree at target, echo it.
# Returns non-zero on worktree-add failure so callers can emit failed_infra.
resolve_harness_root() {
  [ -z "$1" ] && { echo "$HOME"; return; }
  _checkout_harness_worktree "$1" "$2"
}

_checkout_harness_worktree() {
  local sha="$1"; local path="$2"
  local repo="${CLAUDE_HARNESS_REPO:-$HOME/.claude}"
  [ -d "$path" ] && { echo "$path"; return; }
  git -C "$repo" worktree add --detach "$path" "$sha" >/dev/null 2>&1 || return 1
  echo "$path"
}
