#!/usr/bin/env bats
# Slice B — cost-feed.sh (SubagentStop hook).
# Captures per-spawn token usage to ~/.claude/metrics/costs.jsonl
# for /eval-model-effectiveness analysis.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK="$REPO_ROOT/hooks/cost-feed.sh"
  TMP="$(mktemp -d -t cf.XXXXXX)"
  export HOME="$TMP"
  export CLAUDE_SESSION_ID="cf-test-$$"
  # HARNESS_ROOT -> repo so the hook can source its _lib (log.sh, cost-helpers);
  # HARNESS_DATA stays $HOME/.claude (where COSTS is asserted) since we do NOT
  # set CLAUDE_CONFIG_DIR/CLAUDE_PLUGIN_DATA.
  export CLAUDE_PLUGIN_ROOT="$REPO_ROOT"
  mkdir -p "$TMP/.claude/pipeline-state" "$TMP/.claude/metrics"
  COSTS="$TMP/.claude/metrics/costs.jsonl"
  unset CLAUDE_SUBAGENT_TYPE CLAUDE_SUBAGENT_MODEL CLAUDE_HOOK_PROFILE
}

teardown() {
  [ -d "$TMP" ] && rm -rf "$TMP"
}

_realistic_payload() {
  printf '{"subagent_type":"software-engineer","model":"claude-opus-4-7","usage":{"input_tokens":1000,"output_tokens":500,"cache_read_input_tokens":2000}}'
}

@test "T1 hook file exists and is executable" {
  [ -f "$HOOK" ]
  [ -x "$HOOK" ] || bash -n "$HOOK"
}

@test "T2 missing usage field → exit 0, no record written" {
  local input='{"subagent_type":"software-engineer"}'
  run bash -c "echo '$input' | bash $HOOK"
  [ "$status" -eq 0 ]
  [ ! -f "$COSTS" ] || [ "$(wc -l < "$COSTS" | tr -d ' ')" = "0" ]
}

@test "T3 all-zero usage → exit 0, no record written" {
  local input='{"subagent_type":"software-engineer","usage":{"input_tokens":0,"output_tokens":0,"cache_read_input_tokens":0}}'
  run bash -c "echo '$input' | bash $HOOK"
  [ "$status" -eq 0 ]
  [ ! -f "$COSTS" ] || [ "$(wc -l < "$COSTS" | tr -d ' ')" = "0" ]
}

@test "T4 realistic payload writes a JSONL record with required fields" {
  local input; input="$(_realistic_payload)"
  run bash -c "echo '$input' | bash $HOOK"
  [ "$status" -eq 0 ]
  [ -f "$COSTS" ]
  [ "$(wc -l < "$COSTS" | tr -d ' ')" = "1" ]
  grep -q '"agent_role":"software-engineer"' "$COSTS"
  grep -q '"model":"claude-opus-4-7"' "$COSTS"
  grep -q '"input_tokens":1000' "$COSTS"
  grep -q '"output_tokens":500' "$COSTS"
  grep -q '"cached_tokens":2000' "$COSTS"
  grep -q '"rate_version":"opus-4-7-2026-04"' "$COSTS"
  grep -q '"session_id":"cf-test-' "$COSTS"
}

@test "T5 cost computed with Opus 4.7 rates: (i*5 + o*25 + c*0.5)/1e6" {
  # 1000*5 + 500*25 + 2000*0.5 = 5000 + 12500 + 1000 = 18500
  # 18500 / 1_000_000 = 0.0185
  local input; input="$(_realistic_payload)"
  bash -c "echo '$input' | bash $HOOK"
  grep -qE '"total_cost_usd":0\.018[45]' "$COSTS"
}

@test "T6 pipeline_id resolved from newest-mtime *-pipeline.md" {
  echo "old" > "$TMP/.claude/pipeline-state/old-pipeline.md"
  sleep 1
  echo "new" > "$TMP/.claude/pipeline-state/active-pipeline.md"
  local input; input="$(_realistic_payload)"
  bash -c "echo '$input' | bash $HOOK"
  grep -q '"pipeline_id":"active"' "$COSTS"
}

@test "T7 pipeline_id falls back to \"none\" when no pipeline files" {
  local input; input="$(_realistic_payload)"
  bash -c "echo '$input' | bash $HOOK"
  grep -q '"pipeline_id":"none"' "$COSTS"
}

@test "T8 agent_role missing in JSON falls back to CLAUDE_SUBAGENT_TYPE env" {
  local input='{"usage":{"input_tokens":100,"output_tokens":50,"cache_read_input_tokens":0}}'
  CLAUDE_SUBAGENT_TYPE=qa-engineer run bash -c "echo '$input' | bash $HOOK"
  [ "$status" -eq 0 ]
  grep -q '"agent_role":"qa-engineer"' "$COSTS"
}

@test "T9 agent_role unknown when not in JSON or env" {
  local input='{"usage":{"input_tokens":100,"output_tokens":50,"cache_read_input_tokens":0}}'
  run bash -c "echo '$input' | bash $HOOK"
  [ "$status" -eq 0 ]
  grep -q '"agent_role":"unknown"' "$COSTS"
}

@test "T10 model missing in JSON falls back to CLAUDE_SUBAGENT_MODEL env" {
  local input='{"subagent_type":"x","usage":{"input_tokens":100,"output_tokens":50,"cache_read_input_tokens":0}}'
  CLAUDE_SUBAGENT_MODEL=claude-sonnet-4-6 run bash -c "echo '$input' | bash $HOOK"
  grep -q '"model":"claude-sonnet-4-6"' "$COSTS"
}

@test "T11 model unknown when not in JSON or env" {
  local input='{"subagent_type":"x","usage":{"input_tokens":100,"output_tokens":50,"cache_read_input_tokens":0}}'
  run bash -c "echo '$input' | bash $HOOK"
  grep -q '"model":"unknown"' "$COSTS"
}

@test "T12 timestamp is ISO 8601 UTC" {
  local input; input="$(_realistic_payload)"
  bash -c "echo '$input' | bash $HOOK"
  grep -qE '"timestamp":"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z"' "$COSTS"
}

@test "T13 malformed JSON input → exit 0, no crash, no record" {
  local input='{not valid json'
  run bash -c "printf '%s' '$input' | bash $HOOK"
  [ "$status" -eq 0 ]
  [ ! -f "$COSTS" ] || [ "$(wc -l < "$COSTS" | tr -d ' ')" = "0" ]
}

@test "T14 empty stdin → exit 0, no record" {
  run bash -c "printf '' | bash $HOOK"
  [ "$status" -eq 0 ]
  [ ! -f "$COSTS" ] || [ "$(wc -l < "$COSTS" | tr -d ' ')" = "0" ]
}

@test "T15 non-zero output_tokens only (input=0, cache=0) still writes record" {
  local input='{"subagent_type":"x","usage":{"input_tokens":0,"output_tokens":50,"cache_read_input_tokens":0}}'
  run bash -c "echo '$input' | bash $HOOK"
  [ "$status" -eq 0 ]
  [ -f "$COSTS" ]
  [ "$(wc -l < "$COSTS" | tr -d ' ')" = "1" ]
}

@test "T16 hook is registered in settings.json under SubagentStop" {
  # Hook entries were hardened to the fail-safe `bash -lc '...'` wrapper form,
  # so the script name lives in args, not .command. Match across command+args.
  local settings="$REPO_ROOT/settings.json"
  jq -e '.hooks.SubagentStop[].hooks[]
         | select(([.command] + (.args // [])) | join(" ") | test("cost-feed.sh"))' \
     "$settings" >/dev/null
}

@test "T17 hook file ≤50 LOC" {
  local n; n=$(wc -l < "$HOOK" | tr -d ' ')
  [ "$n" -le 50 ]
}

@test "T18 every function body ≤5 lines (excluding signature/closing brace)" {
  # Walk function defs, count body lines between { and }.
  local helpers="$REPO_ROOT/hooks/_lib/cost-helpers.sh"
  local files=("$HOOK")
  [ -f "$helpers" ] && files+=("$helpers")
  for f in "${files[@]}"; do
    awk '
      /^[a-zA-Z_][a-zA-Z0-9_]*\(\)[ ]*\{/ { in_fn=1; lines=0; name=$1; next }
      in_fn && /^\}[ ]*$/ { if (lines > 5) { print FILENAME":"name" body="lines; bad=1 } in_fn=0; next }
      in_fn { lines++ }
      END { exit bad }
    ' "$f"
  done
}

@test "T19 shellcheck clean" {
  command -v shellcheck >/dev/null 2>&1 || skip "shellcheck not installed"
  shellcheck "$HOOK"
  [ -f "$REPO_ROOT/hooks/_lib/cost-helpers.sh" ] && shellcheck "$REPO_ROOT/hooks/_lib/cost-helpers.sh"
  return 0
}
