#!/usr/bin/env bats
# Approval token gate — Wave 4-N
# Tests for hooks/_lib/approval-token.sh and skills/pr-creation/lib/check-approval-token.sh

setup() {
  BATS_FILE_TMPDIR="$(mktemp -d -t approvaltoken.XXXXXX)"
  export HOME="$BATS_FILE_TMPDIR"
  export CLAUDE_SESSION_ID="test-$$"
  mkdir -p "$HOME/.claude/pipeline-state"
  mkdir -p "$HOME/.claude/metrics/$CLAUDE_SESSION_ID"
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  source "$REPO_ROOT/hooks/_lib/approval-token.sh"
}

teardown() {
  rm -rf "$BATS_FILE_TMPDIR"
}

@test "_at_token_path: returns expected path under HOME" {
  run _at_token_path "wave4-N"
  [ "$status" -eq 0 ]
  [ "$output" = "$HOME/.claude/pipeline-state/wave4-N-approval.token" ]
}

@test "_at_resolve_task_id: empty branch returns empty string" {
  run _at_resolve_task_id ""
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "_at_resolve_task_id: main returns empty string" {
  run _at_resolve_task_id "main"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "_at_resolve_task_id: master returns empty string" {
  run _at_resolve_task_id "master"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "_at_resolve_task_id: build/wave4-N returns wave4-N" {
  run _at_resolve_task_id "build/wave4-N"
  [ "$status" -eq 0 ]
  [ "$output" = "wave4-N" ]
}

@test "_at_resolve_task_id: build/wave4-N/slice-1 returns slice-1 (last segment)" {
  run _at_resolve_task_id "build/wave4-N/slice-1"
  [ "$status" -eq 0 ]
  [ "$output" = "slice-1" ]
}

@test "_at_resolve_task_id: feature/wave4-N returns wave4-N" {
  run _at_resolve_task_id "feature/wave4-N"
  [ "$status" -eq 0 ]
  [ "$output" = "wave4-N" ]
}

@test "_at_pipeline_active: returns 0 when pipeline file exists" {
  touch "$HOME/.claude/pipeline-state/task1-pipeline.md"
  run _at_pipeline_active "task1"
  [ "$status" -eq 0 ]
}

@test "_at_pipeline_active: returns 1 when pipeline file is missing" {
  run _at_pipeline_active "task-missing"
  [ "$status" -eq 1 ]
}

@test "_at_token_exists: returns 1 when token file is absent" {
  run _at_token_exists "missing-task"
  [ "$status" -eq 1 ]
}

@test "_at_token_verdict: returns MISSING when file is absent" {
  run _at_token_verdict "missing-task"
  [ "$status" -eq 0 ]
  [ "$output" = "MISSING" ]
}

@test "_at_write_token APPROVED + _at_token_exists: file is present after write" {
  run _at_write_token "task-A" "APPROVED"
  [ "$status" -eq 0 ]
  run _at_token_exists "task-A"
  [ "$status" -eq 0 ]
}
