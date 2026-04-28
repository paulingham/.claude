#!/usr/bin/env bash
# Auto-PR preflight helpers — extracted from auto-pr.sh for 50-line shape compliance
# (auto-pr.sh was 54 lines pre-wave4-N; token-gate addition would have pushed it to ~60 lines)
# Source this file; call _apf_* functions.

_apf_resolve_branch() {
  local branch; branch="$(git branch --show-current 2>/dev/null || echo "")"
  branch="${branch//[^a-zA-Z0-9\/_.-]/}"
  [ "$branch" = "main" ] || [ "$branch" = "master" ] && return 0
  echo "$branch"
}

_apf_resolve_base() {
  git rev-parse main >/dev/null 2>&1 && { echo "main"; return 0; }
  git rev-parse master >/dev/null 2>&1 && { echo "master"; return 0; }
}

_apf_commits_ahead() {
  git log "$1..HEAD" --oneline 2>/dev/null | wc -l | tr -d ' '
}

_apf_uncommitted_count() {
  git status --porcelain 2>/dev/null | wc -l | tr -d ' '
}
