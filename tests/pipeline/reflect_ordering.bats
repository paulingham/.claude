#!/usr/bin/env bats
# tests/pipeline/reflect_ordering.bats
#
# Pins the reflect-before-ship ordering invariant from
# pipeline-state/reflect-before-ship/plan.md.
#
# The reordering relocates observation append + /learn (formerly post-Ship
# in skills/pipeline/SKILL.md Step 7b-bis + 7c) to a NEW Step 4d
# (Reflect-write) that runs BEFORE Step 4c (Multi-Repo Ship → /pr-creation).
# This guarantees the orchestrator commits observation + instinct files to
# the feature-branch worktree, so learning artifacts ship inside the PR
# instead of landing as orphan `chore(learning):` commits on local main.
#
# These tests are pure markdown contract checks — they grep line numbers
# in the source files and assert the relative ordering. No subprocess
# dispatch, no /pipeline invocation.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  SKILL="$REPO_ROOT/skills/pipeline/SKILL.md"
  REFLECT="$REPO_ROOT/protocols/reflection-protocol.md"
}

# Helper: line number of first match for an exact-grep pattern. Empty when
# no match. Use grep -nF for fixed strings.
_line() {
  grep -nF -m1 "$2" "$1" 2>/dev/null | head -1 | cut -d: -f1
}

@test "Step 4d appears before Step 4c in pipeline SKILL.md" {
  l4d="$(_line "$SKILL" "### Step 4d: Reflect-write")"
  l4c="$(_line "$SKILL" "### Step 4c: Multi-Repo Ship")"
  [ -n "$l4d" ]
  [ -n "$l4c" ]
  [ "$l4d" -lt "$l4c" ]
}

@test "Step 4c notes Step 4d prerequisite" {
  # Within the Step 4c block body (between its header and the next ###),
  # 'Step 4d' must appear at least once.
  l4c="$(_line "$SKILL" "### Step 4c: Multi-Repo Ship")"
  [ -n "$l4c" ]
  # Find the next ### header strictly after 4c.
  next_header_line="$(awk -v start="$l4c" 'NR>start && /^### / {print NR; exit}' "$SKILL")"
  [ -n "$next_header_line" ]
  # Extract block lines (exclusive of next header).
  block="$(sed -n "${l4c},$((next_header_line - 1))p" "$SKILL")"
  echo "$block" | grep -qF "Step 4d"
}

@test "Step 7d cleanup remains after Step 5 and Step 6" {
  l7d="$(_line "$SKILL" "#### 7d. Reflect Cleanup")"
  l5="$(_line "$SKILL" "### Step 5: Deploy")"
  l6="$(_line "$SKILL" "### Step 6: Completion")"
  [ -n "$l7d" ]
  [ -n "$l5" ]
  [ -n "$l6" ]
  [ "$l7d" -gt "$l5" ]
  [ "$l7d" -gt "$l6" ]
}

@test "reflection-protocol.md references Step 4d for learning writes" {
  run grep -c "Step 4d" "$REFLECT"
  [ "$status" -eq 0 ]
  [ "$output" -ge 1 ]
}

@test "observation append and /learn precede /pr-creation in SKILL.md" {
  # observation append: the first observations.jsonl mention is in Step 4d.
  l_obs="$(_line "$SKILL" "observations.jsonl")"
  # /learn invocation: first 'Invoke `/learn`' line is in Step 4d-ii.
  l_learn="$(_line "$SKILL" "Invoke \`/learn\`")"
  # /pr-creation: Step 4c body invokes it.
  l_pr="$(_line "$SKILL" "/pr-creation")"
  [ -n "$l_obs" ]
  [ -n "$l_learn" ]
  [ -n "$l_pr" ]
  # max(obs, learn) < pr
  max_lhs="$l_obs"
  if [ "$l_learn" -gt "$max_lhs" ]; then max_lhs="$l_learn"; fi
  [ "$max_lhs" -lt "$l_pr" ]
}
