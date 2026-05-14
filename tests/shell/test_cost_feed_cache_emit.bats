#!/usr/bin/env bats
# Slice A — cost-feed.sh per-session cache.jsonl emit (AC-A1, AC-A3).
#
# Extends cost-feed.sh to also emit metrics/{session}/cache.jsonl alongside
# the existing global metrics/costs.jsonl. Hybrid producer is intentional —
# see header comment of hooks/cost-feed.sh § "Hybrid producer:" rationale.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK="$REPO_ROOT/hooks/cost-feed.sh"
  TMP="$(mktemp -d -t cfce.XXXXXX)"
  export HOME="$TMP"
  export CLAUDE_SESSION_ID="cfce-test-$$"
  mkdir -p "$TMP/.claude/pipeline-state" "$TMP/.claude/metrics"
  CACHE_DIR="$TMP/.claude/metrics/$CLAUDE_SESSION_ID"
  CACHE="$CACHE_DIR/cache.jsonl"
  unset CLAUDE_SUBAGENT_TYPE CLAUDE_SUBAGENT_MODEL CLAUDE_HOOK_PROFILE
}

teardown() {
  [ -d "$TMP" ] && rm -rf "$TMP"
}

@test "cost-feed.sh emits metrics/{session}/cache.jsonl with required fields when usage block carries cache_read_input_tokens" {
  local input='{"subagent_type":"software-engineer","model":"claude-opus-4-7","usage":{"input_tokens":1000,"output_tokens":500,"cache_read_input_tokens":2000,"cache_creation_input_tokens":300}}'
  run bash -c "echo '$input' | bash $HOOK"
  [ "$status" -eq 0 ]
  [ -f "$CACHE" ]
  [ "$(wc -l < "$CACHE" | tr -d ' ')" = "1" ]
  grep -q '"agent_role":"software-engineer"' "$CACHE"
  grep -q '"input_tokens":1000' "$CACHE"
  grep -q '"cache_read_input_tokens":2000' "$CACHE"
  grep -q '"cache_creation_input_tokens":300' "$CACHE"
  grep -q '"session_id":"cfce-test-' "$CACHE"
  grep -q '"ts":"' "$CACHE"
  # read_ratio = 2000 / (2000 + 300 + 1000) = 2000/3300 = 0.6060...
  grep -qE '"read_ratio":0\.60[0-9]+' "$CACHE"
}

@test "cost-feed.sh writes no cache.jsonl record when usage block is all zeros including cache_create" {
  local input='{"subagent_type":"x","usage":{"input_tokens":0,"output_tokens":0,"cache_read_input_tokens":0,"cache_creation_input_tokens":0}}'
  run bash -c "echo '$input' | bash $HOOK"
  [ "$status" -eq 0 ]
  [ ! -f "$CACHE" ] || [ "$(wc -l < "$CACHE" | tr -d ' ')" = "0" ]
}

@test "cost-feed.sh emits cache.jsonl record for pure cache-hit (cache_read>0, cache_create=0, input=0)" {
  # Subagent-summary cache-fix path: fully cache-hit responses.
  local input='{"subagent_type":"software-engineer","model":"claude-opus-4-7","usage":{"input_tokens":0,"output_tokens":50,"cache_read_input_tokens":5000,"cache_creation_input_tokens":0}}'
  run bash -c "echo '$input' | bash $HOOK"
  [ "$status" -eq 0 ]
  [ -f "$CACHE" ]
  # read_ratio = 5000 / (5000 + 0 + 0) = 1.0
  grep -qE '"read_ratio":1(\.0+)?' "$CACHE"
}

@test "cost-feed.sh still writes global costs.jsonl alongside per-session cache.jsonl (hybrid producer)" {
  local input='{"subagent_type":"software-engineer","model":"claude-opus-4-7","usage":{"input_tokens":1000,"output_tokens":500,"cache_read_input_tokens":2000,"cache_creation_input_tokens":300}}'
  run bash -c "echo '$input' | bash $HOOK"
  [ "$status" -eq 0 ]
  [ -f "$TMP/.claude/metrics/costs.jsonl" ]
  [ -f "$CACHE" ]
}
