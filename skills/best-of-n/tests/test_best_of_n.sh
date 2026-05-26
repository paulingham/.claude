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

winner="$(printf 'good|%s|3|20|1\nbad|%s|5|50|1\n' "$good_score" "$bad_score" | pick_winner)"
assert_eq "good" "$winner" "winner selection"

# Slice C — Best-of-N tie-breaker file-count split
# Records are 5 fields: name|score|changed_files|changed_lines|cost_rank
# Sort key: score DESC primary, then (changed_files, changed_lines, cost_rank) ASC.

# Tier 0 — sort flags encode the canonical tuple in this exact order.
# `|| true` keeps `set -e`/pipefail from killing the script on a non-match;
# the absence of a match is what we assert against, not a script-fatal error.
sort_flags_match="$(grep -E -o "sort[[:space:]]+-t[\"']\\|[\"'][[:space:]]+-k2,2nr[[:space:]]+-k3,3n[[:space:]]+-k4,4n[[:space:]]+-k5,5n" "$LIB" || true)"
if [ -n "$sort_flags_match" ]; then
  echo "PASS: pick_winner sort flags encode the canonical tuple"
else
  echo "FAIL: pick_winner sort flags encode the canonical tuple (expected '-k2,2nr -k3,3n -k4,4n -k5,5n' literal in $LIB)" >&2
  exit 1
fi

# C1 — pick_winner accepts a single 5-field record.
single="$(printf 'cand|100|3|50|1\n' | pick_winner)"
assert_eq "cand" "$single" "pick_winner accepts 5-field record"

# C2 — score DESC remains the primary key.
score_primary="$(printf 'low|100|3|50|1\nhigh|200|3|50|1\n' | pick_winner)"
assert_eq "high" "$score_primary" "score DESC primary key"

# C3 — file-count is the FIRST tie-breaker (equal score, equal lines, differ files).
files_first="$(printf 'a|100|5|100|1\nb|100|3|100|1\n' | pick_winner)"
assert_eq "b" "$files_first" "file-count tie-breaker first"

# C4 — line-count is the SECOND tie-breaker (equal score, equal files, differ lines).
lines_second="$(printf 'a|100|3|100|1\nb|100|3|50|1\n' | pick_winner)"
assert_eq "b" "$lines_second" "line-count tie-breaker second"

# C5 — cost-rank is the THIRD tie-breaker (equal score+files+lines, differ rank).
cost_third="$(printf 'a|100|3|50|2\nb|100|3|50|1\n' | pick_winner)"
assert_eq "b" "$cost_third" "cost-rank tie-breaker third"

# C6 — file-count beats line-count when both differ in opposing directions.
files_beat_lines="$(printf 'a|100|5|100|1\nb|100|3|200|1\n' | pick_winner)"
assert_eq "b" "$files_beat_lines" "file-count beats line-count when both differ"

# C7 — config.json::tie_breaker_order is the ordered triple.
CONFIG_JSON="${SCRIPT_DIR}/../config.json"
tie_breaker_order="$(jq -r '.tie_breaker_order | join(",")' "$CONFIG_JSON")"
assert_eq "changed_files_asc,changed_lines_asc,cost_asc" "$tie_breaker_order" \
  "config.json tie_breaker_order is the ordered triple"

# C8 — script-config tie-breaker order consistency.
# Parse script's tie-breaker fields (excluding the score primary -k2,2nr) and map to
# the canonical config token list. -k3 -> changed_files_asc; -k4 -> changed_lines_asc;
# -k5 -> cost_asc. `|| true` so an empty grep does not abort the test under pipefail
# — we assert on the captured value, not on grep's exit code. xargs collapses
# whitespace and strips trailing newlines deterministically.
script_tb_fields="$(grep -E -o "\\-k[3-9],[0-9]+n" "$LIB" || true)"
script_tb_fields="$(printf '%s' "$script_tb_fields" | xargs)"
expected_script_tb_fields="-k3,3n -k4,4n -k5,5n"
assert_eq "$expected_script_tb_fields" "$script_tb_fields" \
  "script and config tie-breaker order consistency"

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

# AC3 — max_candidates config pinning (regression guard).
# config.json must declare max_candidates: 3 — changing this silently would
# allow unbounded fan-out; the test prevents accidental drift.
CONFIG_JSON="${SCRIPT_DIR}/../config.json"
max_candidates_val="$(jq -r '.max_candidates' "$CONFIG_JSON")"
assert_eq "3" "$max_candidates_val" "max_candidates_config_pinned"

# AC3 — dispatcher prose contains an upper-bound guard for max_candidates.
DISPATCHER="${SCRIPT_DIR}/../../../orchestrator/parallel-dispatch-details.md"
if grep -qE "max_candidates.*upper bound|upper bound.*max_candidates" "$DISPATCHER"; then
  echo "PASS: max_candidates_cap_enforced_in_dispatcher"
else
  echo "FAIL: max_candidates_cap_enforced_in_dispatcher (upper bound prose not found in $DISPATCHER)" >&2
  exit 1
fi

echo "ALL TESTS PASSED"
