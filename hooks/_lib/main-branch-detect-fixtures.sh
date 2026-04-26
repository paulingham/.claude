#!/usr/bin/env bash
# Test-fixture helpers for main-branch-detect — used only by bats specs,
# NOT by the guard at runtime (the guard inspects command strings only).
# Sourced by hermetic test setup in tests/shell/test_main_branch_detect.bats.

is_in_main_tree() {
  local common_dir git_dir
  common_dir=$(cd "$1" 2>/dev/null && cd "$(git rev-parse --git-common-dir 2>/dev/null)" 2>/dev/null && pwd -P) || return 1
  git_dir=$(cd "$1" 2>/dev/null && cd "$(git rev-parse --git-dir 2>/dev/null)" 2>/dev/null && pwd -P) || return 1
  [[ "$common_dir" == "$git_dir" ]]
}

is_in_worktree() { is_in_main_tree "$1" && return 1 || return 0; }
