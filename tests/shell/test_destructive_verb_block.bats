#!/usr/bin/env bats
# Wave-2 A4.2 — destructive-verb module test for main-branch-guard.
# Verifies:
#   - Each verb in destructive-verbs.txt blocks (exit 2) without confirmation token
#   - Confirmation token within TTL allows the command through (back to standard MBG checks)
#   - Confirmation token past TTL still blocks
#   - Wrong confirmation token value blocks
#   - JSONL violation record is written with source: "destructive-verb"

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK="$REPO_ROOT/hooks/main-branch-guard.sh"
  TMP="$(mktemp -d -t dvb.XXXXXX)"
  export HOME="$TMP"
  export CLAUDE_SESSION_ID="dvb-test-$$"
  export CLAUDE_HOOK_PROFILE="minimal"  # ensure the guard runs
  unset CLAUDE_DESTRUCTIVE_CONFIRM CLAUDE_DESTRUCTIVE_CONFIRM_TS CLAUDE_DESTRUCTIVE_CONFIRM_TTL
  mkdir -p "$TMP/.claude"
}

teardown() {
  [ -d "$TMP" ] && rm -rf "$TMP"
}

_run_hook() {
  local cmd="$1"
  local payload
  payload=$(jq -nc --arg c "$cmd" '{tool_name:"Bash",tool_input:{command:$c}}')
  echo "$payload" | bash "$HOOK"
}

@test "DV1 volumeDelete blocks without confirmation" {
  run _run_hook "fly volumes destroy vol_abc123 || volumeDelete vol_abc123"
  [ "$status" -eq 2 ]
  echo "$output" | grep -q "destructive verb"
}

@test "DV2 DROP TABLE blocks without confirmation" {
  run _run_hook "psql -c 'DROP TABLE users'"
  [ "$status" -eq 2 ]
}

@test "DV3 TRUNCATE blocks without confirmation" {
  run _run_hook "psql -c 'TRUNCATE users'"
  [ "$status" -eq 2 ]
}

@test "DV4 aws s3 rb blocks without confirmation" {
  run _run_hook "aws s3 rb s3://prod-bucket --force"
  [ "$status" -eq 2 ]
}

@test "DV5 gcloud sql instances delete blocks" {
  run _run_hook "gcloud sql instances delete prod-db"
  [ "$status" -eq 2 ]
}

@test "DV6 railway down blocks" {
  run _run_hook "railway down"
  [ "$status" -eq 2 ]
}

@test "DV7 fly destroy blocks" {
  run _run_hook "fly destroy my-app"
  [ "$status" -eq 2 ]
}

@test "DV8 force-with-lease to main blocks" {
  run _run_hook "git push --force-with-lease origin main"
  [ "$status" -eq 2 ]
}

@test "DV9 rm -rf \$HOME blocks" {
  run _run_hook 'rm -rf $HOME/important'
  [ "$status" -eq 2 ]
}

@test "DV10 kubectl delete namespace prod blocks" {
  run _run_hook "kubectl delete namespace prod"
  [ "$status" -eq 2 ]
}

@test "DV11 confirmation token within TTL allows through" {
  export CLAUDE_DESTRUCTIVE_CONFIRM="I-have-a-restorable-backup-elsewhere"
  export CLAUDE_DESTRUCTIVE_CONFIRM_TS=$(date +%s)
  run _run_hook "psql -c 'TRUNCATE logs'"
  # No destructive-verb block; standard MBG passes (not a HEAD-mutating cmd) → exit 0.
  [ "$status" -eq 0 ]
}

@test "DV12 confirmation token expired (past 600s) blocks" {
  export CLAUDE_DESTRUCTIVE_CONFIRM="I-have-a-restorable-backup-elsewhere"
  export CLAUDE_DESTRUCTIVE_CONFIRM_TS=$(( $(date +%s) - 700 ))
  run _run_hook "psql -c 'DROP TABLE logs'"
  [ "$status" -eq 2 ]
}

@test "DV13 wrong confirmation token value blocks" {
  export CLAUDE_DESTRUCTIVE_CONFIRM="yes-do-it"
  export CLAUDE_DESTRUCTIVE_CONFIRM_TS=$(date +%s)
  run _run_hook "psql -c 'DROP TABLE logs'"
  [ "$status" -eq 2 ]
}

@test "DV14 JSONL violation record written" {
  run _run_hook "fly destroy my-app"
  [ "$status" -eq 2 ]
  jsonl="$TMP/.claude/metrics/$CLAUDE_SESSION_ID/main-branch-violations.jsonl"
  [ -f "$jsonl" ]
  grep -q '"source":"destructive-verb"' "$jsonl"
  grep -q '"action":"prevented"' "$jsonl"
}

@test "DV15 non-destructive command passes through" {
  run _run_hook "ls -la"
  [ "$status" -eq 0 ]
}

@test "DV16 short TTL override (CLAUDE_DESTRUCTIVE_CONFIRM_TTL) honored" {
  export CLAUDE_DESTRUCTIVE_CONFIRM="I-have-a-restorable-backup-elsewhere"
  export CLAUDE_DESTRUCTIVE_CONFIRM_TS=$(( $(date +%s) - 30 ))
  export CLAUDE_DESTRUCTIVE_CONFIRM_TTL=10
  run _run_hook "psql -c 'DROP TABLE logs'"
  [ "$status" -eq 2 ]
}
