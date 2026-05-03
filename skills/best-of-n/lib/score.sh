#!/usr/bin/env bash
# Pure-bash scoring helpers for /best-of-n. Integer math only.
# Exports: score_candidate, pick_winner, check_budget_gate, check_worktree_capacity.
#
# DEPRECATED-IN-PLACE: budget-only threshold sub-check.
# The authoritative Best-of-N gate is hooks/_lib/bestofn_gate.py.

score_candidate() {
  local test_pass="$1" violations="$2" quality="$3" diff="$4"
  local shape=$(( 10 - violations ))
  [ "$shape" -lt 0 ] && shape=0
  echo $(( test_pass*1000 + shape*10 + quality*20 - diff/100 ))
}

pick_winner() {
  sort -t'|' -k2,2nr -k3,3n -k4,4n | head -n1 | cut -d'|' -f1
}

check_budget_gate() {
  local budget="$1"
  [ "$budget" -ge 5 ] && echo "OK" || echo "WRONG_SKILL"
}

# Wave-2 B11.2 — pre-flight worktree resource check.
# Best-of-N spawns one worktree per candidate (typically 2-3). When the host
# already has many active worktrees (parallel sessions, abandoned pipelines),
# adding more triggers disk/inode pressure that has caused build flakes.
# This helper returns "OK" when the repo's current worktree count is under
# the env-configured cap, "fallback-to-single-engineer" otherwise.
#
# Defaults: 6 worktrees on workstations, 12 on CI (CI=true). Override with
# CLAUDE_BESTOFN_MAX_WORKTREES.
_bon_worktree_cap() {
  local cap="${CLAUDE_BESTOFN_MAX_WORKTREES:-}"
  if [ -n "$cap" ]; then printf '%s' "$cap"; return; fi
  if [ "${CI:-false}" = "true" ]; then printf '12'; else printf '6'; fi
}

_bon_worktree_count() {
  local repo="${1:-.}"
  git -C "$repo" worktree list --porcelain 2>/dev/null | grep -c '^worktree ' || echo 0
}

check_worktree_capacity() {
  local repo="${1:-.}" cap count
  cap=$(_bon_worktree_cap)
  count=$(_bon_worktree_count "$repo")
  [ "$count" -lt "$cap" ] && echo "OK" || echo "fallback-to-single-engineer"
}

export -f score_candidate pick_winner check_budget_gate check_worktree_capacity \
          _bon_worktree_cap _bon_worktree_count
