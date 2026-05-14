#!/usr/bin/env bats
# _qg_check_freshness must auto-pass for T0/T1 intake tiers (docs-only / question).
#
# Motivation: PR #139 was a .md-only T1 change. The freshness gate blocked
# `gh pr create` because no verification-evidence.json existed — even though
# /verify legitimately never ran (no source-code surface). T0/T1 carve out;
# T2-T6 retain the original behaviour (file-exists → git_head → verdict prefix).

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  CHECKS_SH="$REPO_ROOT/hooks/_lib/quality-gate-checks.sh"
  TMP_DIR="$(mktemp -d -t freshness-tier-carveout-XXXXXX)"
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

# --- AC1: T1 auto-passes ----------------------------------------------------

@test "T1 intake auto-passes with docs-only message" {
  write_intake t1-task '---
task_id: t1-task
tier_emitted: T1
---'
  run_freshness t1-task
  [ "$status" -eq 0 ]
  [[ "$output" == *"[freshness] PASS (tier=T1; docs-only, /verify not applicable)"* ]]
}

# --- AC1: T0 auto-passes (no evidence file) ---------------------------------

@test "T0 intake auto-passes even without verification-evidence" {
  write_intake t0-task '---
tier_emitted: T0
---'
  run_freshness t0-task
  [ "$status" -eq 0 ]
  [[ "$output" == *"[freshness] PASS (tier=T0; docs-only, /verify not applicable)"* ]]
}

# --- AC3: T2 does NOT carve out ---------------------------------------------

@test "T2 intake does NOT auto-pass; preserves no-evidence failure" {
  write_intake t2-task '---
tier_emitted: T2
---'
  run_freshness t2-task
  [ "$status" -eq 1 ]
  [[ "$output" == *"no verification-evidence"* ]]
}

# --- AC2: missing intake.md → original behaviour preserved ------------------

@test "Missing intake.md preserves original no-evidence failure" {
  run_freshness ghost-task
  [ "$status" -eq 1 ]
  [[ "$output" == *"no verification-evidence"* ]]
}

# --- AC2: tier field missing → original behaviour preserved -----------------

@test "intake.md without tier field preserves original behaviour" {
  write_intake bare-task '---
task_id: bare-task
classification: feature
---'
  run_freshness bare-task
  [ "$status" -eq 1 ]
  [[ "$output" == *"no verification-evidence"* ]]
}

# --- AC5: quoted tier value accepted ----------------------------------------

@test "Quoted tier value (tier_emitted: \"T1\") auto-passes" {
  write_intake quoted-task '---
tier_emitted: "T1"
---'
  run_freshness quoted-task
  [ "$status" -eq 0 ]
  [[ "$output" == *"tier=T1"* ]]
}

# --- AC5: whitespace tolerance ----------------------------------------------

@test "Leading/trailing whitespace around tier value accepted" {
  write_intake ws-task '---
tier_emitted:    T1
---'
  run_freshness ws-task
  [ "$status" -eq 0 ]
  [[ "$output" == *"tier=T1"* ]]
}

# --- AC5: short-form "tier:" key also accepted (dogfooding stub format) -----

@test "Short-form tier: T1 (no _emitted suffix) auto-passes" {
  write_intake short-task '---
tier: T1
---'
  run_freshness short-task
  [ "$status" -eq 0 ]
  [[ "$output" == *"tier=T1"* ]]
}

# --- AC2: tier_initial alone (no tier_emitted) must NOT match ---------------

@test "tier_initial alone does not trigger carve-out (only tier_emitted/tier counts)" {
  write_intake initial-only '---
tier_initial: T1
---'
  run_freshness initial-only
  [ "$status" -eq 1 ]
  [[ "$output" == *"no verification-evidence"* ]]
}

# --- AC4: workstream layout preferred when CLAUDE_WORKSTREAM set ------------

@test "Workstream intake.md preferred over root when CLAUDE_WORKSTREAM set" {
  # Root says T5 (would fail); workstream says T1 (should pass).
  write_intake ws-overlap '---
tier_emitted: T5
---'
  mkdir -p "$TMP_DIR/pipeline-state/workstreams/myws/ws-overlap"
  printf -- '---\ntier_emitted: T1\n---\n' \
    > "$TMP_DIR/pipeline-state/workstreams/myws/ws-overlap/intake.md"
  run env -u CLAUDE_DISABLE_FRESHNESS_QG \
    CLAUDE_PIPELINE_TASK_ID=ws-overlap \
    CLAUDE_WORKSTREAM=myws \
    bash -c "cd '$TMP_DIR' && source '$CHECKS_SH' && _qg_check_freshness"
  [ "$status" -eq 0 ]
  [[ "$output" == *"tier=T1"* ]]
}

# --- AC4: workstream missing → falls back to root layout --------------------

@test "Missing workstream intake.md falls back to root layout" {
  write_intake fallback-task '---
tier_emitted: T1
---'
  run env -u CLAUDE_DISABLE_FRESHNESS_QG \
    CLAUDE_PIPELINE_TASK_ID=fallback-task \
    CLAUDE_WORKSTREAM=noexist \
    bash -c "cd '$TMP_DIR' && source '$CHECKS_SH' && _qg_check_freshness"
  [ "$status" -eq 0 ]
  [[ "$output" == *"tier=T1"* ]]
}
