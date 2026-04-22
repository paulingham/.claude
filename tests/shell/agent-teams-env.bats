#!/usr/bin/env bats
# Regression lock: CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS stays "1" (no override).
REPO_ROOT="${BATS_TEST_DIRNAME}/../.."

@test "AC4.1 settings.json top-level CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS is 1" {
  run jq -r '.env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS' "$REPO_ROOT/settings.json"
  [ "$status" -eq 0 ]
  [ "$output" = "1" ]
}

@test "AC4.2 .claude/settings.json does not override the env flag" {
  run jq -r '.env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS // empty' "$REPO_ROOT/.claude/settings.json"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "AC4.3 emits clear reason when top-level flag deviates from 1" {
  local actual
  actual="$(jq -r '.env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS // "<missing>"' "$REPO_ROOT/settings.json")"
  [ "$actual" = "1" ] || {
    printf 'FAIL: settings.json .env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=%s (expected "1")\n' "$actual" >&2
    return 1
  }
}
