#!/usr/bin/env bash
# Integration test for /best-of-n scoring + selection + cleanup + budget gate.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB="${SCRIPT_DIR}/../lib/score.sh"

# shellcheck source=/dev/null
. "$LIB"

REPO_DIR="$(mktemp -d)"
trap 'rm -rf "$REPO_DIR"' EXIT

setup_repo() {
  cd "$REPO_DIR"
  git init -q
  git config user.email bon@test.local
  git config user.name bon
  git config commit.gpgsign false
  git config gpg.format ""
  echo "start" > a.txt
  git add a.txt
  git commit -q -m "init"
}

make_candidate_branch() {
  local name="$1" content="$2"
  git checkout -q -b "build/test-boN-${name}" main 2>/dev/null || git checkout -q -b "build/test-boN-${name}"
  echo "$content" > "${name}.txt"
  git add "${name}.txt"
  git commit -q -m "candidate ${name}"
  git checkout -q main 2>/dev/null || git checkout -q -
}

assert_eq() {
  local expected="$1" actual="$2" label="$3"
  if [ "$expected" = "$actual" ]; then
    echo "PASS: ${label}"
  else
    echo "FAIL: ${label} (expected='${expected}' actual='${actual}')" >&2
    exit 1
  fi
}

setup_repo
git branch -m main 2>/dev/null || true
make_candidate_branch good "fixed"
make_candidate_branch bad "broken"

good_score="$(score_candidate 1 0 4 20)"
bad_score="$(score_candidate 0 3 2 50)"

winner="$(printf 'good|%s|20|1\nbad|%s|50|1\n' "$good_score" "$bad_score" | pick_winner)"
assert_eq "good" "$winner" "winner selection"

git branch -D "build/test-boN-bad" >/dev/null
if git branch | grep -q "build/test-boN-bad"; then
  echo "FAIL: loser cleanup" >&2
  exit 1
fi
echo "PASS: loser cleanup"

gate_below="$(check_budget_gate 4)"
gate_at="$(check_budget_gate 5)"
gate_above="$(check_budget_gate 7)"
assert_eq "WRONG_SKILL" "$gate_below" "budget gate rejects below threshold"
assert_eq "OK" "$gate_at" "budget gate accepts at threshold"
assert_eq "OK" "$gate_above" "budget gate accepts above threshold"

# Wave-2 B11.2 — worktree capacity pre-flight check.
WT_REPO="$(mktemp -d)"
git -C "$WT_REPO" init -q
git -C "$WT_REPO" config user.email t@t
git -C "$WT_REPO" config user.name t
git -C "$WT_REPO" config commit.gpgsign false
git -C "$WT_REPO" config gpg.format ""
echo seed > "$WT_REPO/x"
git -C "$WT_REPO" add -A && git -C "$WT_REPO" commit -q -m init

# 1 active worktree (the main repo) → under default cap of 6 → OK.
unset CI
unset CLAUDE_BESTOFN_MAX_WORKTREES
result_default="$(check_worktree_capacity "$WT_REPO")"
assert_eq "OK" "$result_default" "worktree capacity OK at default workstation cap"

# Custom cap below current count → fallback.
CLAUDE_BESTOFN_MAX_WORKTREES=1 result_at_cap="$(check_worktree_capacity "$WT_REPO")"
assert_eq "fallback-to-single-engineer" "$result_at_cap" \
  "worktree capacity falls back when count >= cap"

# CI cap (12) is higher than workstation cap (6).
unset CLAUDE_BESTOFN_MAX_WORKTREES
ci_cap_count="$(CI=true bash -c 'source '"$LIB"' && _bon_worktree_cap')"
ws_cap_count="$(CI=false bash -c 'source '"$LIB"' && _bon_worktree_cap')"
assert_eq "12" "$ci_cap_count" "CI cap is 12"
assert_eq "6" "$ws_cap_count" "workstation cap is 6"

# Explicit override beats both defaults.
ovr="$(CLAUDE_BESTOFN_MAX_WORKTREES=42 bash -c 'source '"$LIB"' && _bon_worktree_cap')"
assert_eq "42" "$ovr" "explicit env override beats CI/workstation defaults"

rm -rf "$WT_REPO"

echo "ALL TESTS PASSED"
