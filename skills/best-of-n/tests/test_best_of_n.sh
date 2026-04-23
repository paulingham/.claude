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

gate_low="$(check_budget_gate 5)"
gate_high="$(check_budget_gate 7)"
assert_eq "WRONG_SKILL" "$gate_low" "budget gate rejects low budget"
assert_eq "OK" "$gate_high" "budget gate accepts high budget"

echo "ALL TESTS PASSED"
