#!/usr/bin/env bats
# _qg_check_freshness must auto-pass for gear=PAIR intake (docs-only / question /
# config / mechanical-sweep / trivial-code — none of which run /verify).
#
# Motivation: PR #139 was a .md-only doc change. The freshness gate blocked
# `gh pr create` because no verification-evidence.json existed — even though
# /verify legitimately never ran (no source-code surface). PAIR carves out;
# BUILD/PIPELINE retain the original behaviour (file-exists → git_head → verdict prefix).

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  CHECKS_SH="$REPO_ROOT/hooks/_lib/quality-gate-checks.sh"
  TMP_DIR="$(mktemp -d -t freshness-gear-carveout-XXXXXX)"
  (
    cd "$TMP_DIR" &&
    git init -q -b main &&
    git -c user.email=t@t -c user.name=t commit -q --allow-empty -m init
  )
}

teardown() {
  if [ -n "${TMP_DIR:-}" ] && [ -d "$TMP_DIR" ]; then
    find "$TMP_DIR" -type f -delete
    find "$TMP_DIR" -depth -type d -empty -delete
  fi
}

# --- helpers -----------------------------------------------------------------

write_intake() {
  local task="$1" body="$2"
  mkdir -p "$TMP_DIR/pipeline-state/$task"
  printf '%s\n' "$body" > "$TMP_DIR/pipeline-state/$task/intake.md"
}

run_freshness() {
  local task="${1:-stub-task}"
  run env -u CLAUDE_DISABLE_FRESHNESS_QG \
    CLAUDE_PIPELINE_TASK_ID="$task" \
    bash -c "cd '$TMP_DIR' && source '$CHECKS_SH' && _qg_check_freshness"
}

# --- AC1: PAIR auto-passes ---------------------------------------------------

@test "PAIR gear auto-passes with docs-only message" {
  write_intake pair-task '---
task_id: pair-task
gear_emitted: PAIR
---'
  run_freshness pair-task
  [ "$status" -eq 0 ]
  [[ "$output" == *"[freshness] PASS (gear=PAIR; docs-only, /verify not applicable)"* ]]
}

# --- AC1: PAIR auto-passes even without verification-evidence ---------------

@test "PAIR gear auto-passes even without verification-evidence" {
  write_intake pair-no-evidence '---
gear_emitted: PAIR
---'
  run_freshness pair-no-evidence
  [ "$status" -eq 0 ]
  [[ "$output" == *"[freshness] PASS (gear=PAIR; docs-only, /verify not applicable)"* ]]
}

# --- AC3: BUILD does NOT carve out -------------------------------------------

@test "BUILD gear does NOT auto-pass; preserves no-evidence failure" {
  write_intake build-task '---
gear_emitted: BUILD
---'
  run_freshness build-task
  [ "$status" -eq 1 ]
  [[ "$output" == *"no verification-evidence"* ]]
}

# --- AC3: PIPELINE does NOT carve out -----------------------------------------

@test "PIPELINE gear does NOT auto-pass; preserves no-evidence failure" {
  write_intake pipeline-task '---
gear_emitted: PIPELINE
---'
  run_freshness pipeline-task
  [ "$status" -eq 1 ]
  [[ "$output" == *"no verification-evidence"* ]]
}

# --- AC2: missing intake.md → original behaviour preserved ------------------

@test "Missing intake.md preserves original no-evidence failure" {
  run_freshness ghost-task
  [ "$status" -eq 1 ]
  [[ "$output" == *"no verification-evidence"* ]]
}

# --- AC2: gear field missing → original behaviour preserved -----------------

@test "intake.md without gear field preserves original behaviour" {
  write_intake bare-task '---
task_id: bare-task
classification: feature
---'
  run_freshness bare-task
  [ "$status" -eq 1 ]
  [[ "$output" == *"no verification-evidence"* ]]
}

# --- AC5: quoted gear value accepted ----------------------------------------

@test "Quoted gear value (gear_emitted: \"PAIR\") auto-passes" {
  write_intake quoted-task '---
gear_emitted: "PAIR"
---'
  run_freshness quoted-task
  [ "$status" -eq 0 ]
  [[ "$output" == *"gear=PAIR"* ]]
}

# --- AC5: whitespace tolerance ----------------------------------------------

@test "Leading/trailing whitespace around gear value accepted" {
  write_intake ws-task '---
gear_emitted:    PAIR
---'
  run_freshness ws-task
  [ "$status" -eq 0 ]
  [[ "$output" == *"gear=PAIR"* ]]
}

# --- AC5: short-form "gear:" key also accepted (dogfooding stub format) -----

@test "Short-form gear: PAIR (no _emitted suffix) auto-passes" {
  write_intake short-task '---
gear: PAIR
---'
  run_freshness short-task
  [ "$status" -eq 0 ]
  [[ "$output" == *"gear=PAIR"* ]]
}

# --- AC2: gear_initial alone (no gear_emitted) must NOT match ---------------

@test "gear_initial alone does not trigger carve-out (only gear_emitted/gear counts)" {
  write_intake initial-only '---
gear_initial: PAIR
---'
  run_freshness initial-only
  [ "$status" -eq 1 ]
  [[ "$output" == *"no verification-evidence"* ]]
}

# --- AC4: workstream layout preferred when CLAUDE_WORKSTREAM set ------------

@test "Workstream intake.md preferred over root when CLAUDE_WORKSTREAM set" {
  # Root says BUILD (would fail); workstream says PAIR (should pass).
  write_intake ws-overlap '---
gear_emitted: BUILD
---'
  mkdir -p "$TMP_DIR/pipeline-state/workstreams/myws/ws-overlap"
  printf -- '---\ngear_emitted: PAIR\n---\n' \
    > "$TMP_DIR/pipeline-state/workstreams/myws/ws-overlap/intake.md"
  run env -u CLAUDE_DISABLE_FRESHNESS_QG \
    CLAUDE_PIPELINE_TASK_ID=ws-overlap \
    CLAUDE_WORKSTREAM=myws \
    bash -c "cd '$TMP_DIR' && source '$CHECKS_SH' && _qg_check_freshness"
  [ "$status" -eq 0 ]
  [[ "$output" == *"gear=PAIR"* ]]
}

# --- AC4: workstream missing → falls back to root layout --------------------

@test "Missing workstream intake.md falls back to root layout" {
  write_intake fallback-task '---
gear_emitted: PAIR
---'
  run env -u CLAUDE_DISABLE_FRESHNESS_QG \
    CLAUDE_PIPELINE_TASK_ID=fallback-task \
    CLAUDE_WORKSTREAM=noexist \
    bash -c "cd '$TMP_DIR' && source '$CHECKS_SH' && _qg_check_freshness"
  [ "$status" -eq 0 ]
  [[ "$output" == *"gear=PAIR"* ]]
}
