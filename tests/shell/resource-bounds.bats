#!/usr/bin/env bats
# Slice 1 — resource-bounds.sh resolver + settings.json env keys.
# T1.1-T1.4 (AC1.1-AC1.6).

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  unset CLAUDE_SUBAGENT_MAX_DEPTH CLAUDE_SUBAGENT_MAX_RUNTIME CLAUDE_TEAMMATE_MAX_RUNTIME
  # shellcheck source=/dev/null
  source "$REPO_ROOT/hooks/_lib/resource-bounds.sh"
}

@test "T1.1 defaults applied when env unset" {
  [ "$(_max_depth)" = "3" ]
  [ "$(_max_runtime_subagent)" = "1800" ]
  [ "$(_max_runtime_teammate)" = "3600" ]
}

@test "T1.2 env override raises max depth" {
  CLAUDE_SUBAGENT_MAX_DEPTH=5 run _max_depth
  [ "$status" -eq 0 ]
  [ "$output" = "5" ]
}

@test "T1.2b env override on subagent runtime" {
  CLAUDE_SUBAGENT_MAX_RUNTIME=60 run _max_runtime_subagent
  [ "$output" = "60" ]
}

@test "T1.2c env override on teammate runtime" {
  CLAUDE_TEAMMATE_MAX_RUNTIME=120 run _max_runtime_teammate
  [ "$output" = "120" ]
}

@test "T1.3 non-numeric env falls back to default" {
  CLAUDE_SUBAGENT_MAX_DEPTH=foo run _max_depth
  [ "$output" = "3" ]
  CLAUDE_SUBAGENT_MAX_RUNTIME=bar run _max_runtime_subagent
  [ "$output" = "1800" ]
  CLAUDE_TEAMMATE_MAX_RUNTIME=baz run _max_runtime_teammate
  [ "$output" = "3600" ]
}

@test "T1.3b empty env falls back to default" {
  CLAUDE_SUBAGENT_MAX_DEPTH="" run _max_depth
  [ "$output" = "3" ]
}

@test "T1.4 settings.json: live file has the three keys with documented defaults" {
  local f="$REPO_ROOT/settings.json"
  [ -f "$f" ]
  [ "$(jq -r '.env.CLAUDE_SUBAGENT_MAX_DEPTH' "$f")" = "3" ]
  [ "$(jq -r '.env.CLAUDE_SUBAGENT_MAX_RUNTIME' "$f")" = "1800" ]
  [ "$(jq -r '.env.CLAUDE_TEAMMATE_MAX_RUNTIME' "$f")" = "3600" ]
}

@test "T1.4b settings.json: existing env keys still present" {
  local f="$REPO_ROOT/settings.json"
  [ "$(jq -r '.env.CLAUDE_HOOK_PROFILE' "$f")" = "standard" ]
  [ "$(jq -r '.env.CLAUDE_ENABLE_TRACE' "$f")" = "1" ]
  [ "$(jq -r '.env.CLAUDE_CODE_SUBAGENT_MODEL' "$f")" = "opus" ]
}
