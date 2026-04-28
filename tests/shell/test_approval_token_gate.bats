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

@test "_at_token_verdict: round-trips APPROVED after write" {
  _at_write_token "task-B" "APPROVED"
  run _at_token_verdict "task-B"
  [ "$status" -eq 0 ]
  [ "$output" = "APPROVED" ]
}

@test "_at_write_token: invalid verdict GARBAGE exits non-zero, no file written" {
  run _at_write_token "task-C" "GARBAGE"
  [ "$status" -ne 0 ]
  run _at_token_exists "task-C"
  [ "$status" -eq 1 ]
}

@test "_at_write_token APPROVED_WITH_CONDITIONS: verdict round-trips" {
  _at_write_token "task-D" "APPROVED_WITH_CONDITIONS"
  run _at_token_verdict "task-D"
  [ "$status" -eq 0 ]
  [ "$output" = "APPROVED_WITH_CONDITIONS" ]
}

@test "_at_write_token REJECTED: verdict round-trips" {
  _at_write_token "task-E" "REJECTED"
  run _at_token_verdict "task-E"
  [ "$status" -eq 0 ]
  [ "$output" = "REJECTED" ]
}

@test "_at_log_blocked: appends one JSONL line to metrics dir with task_id and reason" {
  _at_log_blocked "task-X" "missing-token"
  local f="$HOME/.claude/metrics/$CLAUDE_SESSION_ID/pr-blocked.jsonl"
  [ -f "$f" ]
  run jq -r '.task_id' "$f"
  [ "$output" = "task-X" ]
  run jq -r '.reason' "$f"
  [ "$output" = "missing-token" ]
}

@test "write-approval-token.sh: writes token file with given verdict" {
  run bash "$REPO_ROOT/hooks/_lib/write-approval-token.sh" --task-id "task-W" --verdict "APPROVED"
  [ "$status" -eq 0 ]
  [ -f "$HOME/.claude/pipeline-state/task-W-approval.token" ]
  run jq -r '.verdict' "$HOME/.claude/pipeline-state/task-W-approval.token"
  [ "$output" = "APPROVED" ]
}

# --- check-approval-token.sh — fixture: stub git branch via PATH override
_stub_branch() {
  local branch="$1"
  local stub_dir="$BATS_FILE_TMPDIR/stub-bin"
  mkdir -p "$stub_dir"
  cat > "$stub_dir/git" <<EOF
#!/usr/bin/env bash
if [ "\$1" = "branch" ] && [ "\$2" = "--show-current" ]; then
  echo "$branch"
  exit 0
fi
exec /usr/bin/env -i PATH=/usr/bin:/bin git "\$@"
EOF
  chmod +x "$stub_dir/git"
  export PATH="$stub_dir:$PATH"
}

@test "check-approval-token.sh: no pipeline file → exit 0, manual PR path message" {
  _stub_branch "feature/no-pipeline-here"
  run bash "$REPO_ROOT/skills/pr-creation/lib/check-approval-token.sh"
  [ "$status" -eq 0 ]
  [[ "$output" == *"manual PR path"* ]]
}
