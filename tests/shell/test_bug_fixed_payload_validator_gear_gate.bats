#!/usr/bin/env bats
# Phase B WS2 — gear-gate for hooks/bug-fixed-payload-validator.sh: BUG_FIXED
# payload-shape enforcement only has meaning for Build/Pipeline gear work
# (Pair-gear workers don't emit structured verdict payloads). No-op in PAIR.
# This hook reads its session id from stdin JSON .session_id (already
# extracted by the hook itself), so the gear fixture is keyed on that value
# directly — no env-var fallback needed here.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK="$REPO_ROOT/hooks/bug-fixed-payload-validator.sh"
  TMP_METRICS="$(mktemp -d -t bfpv-metrics.XXXXXX)"
  TMP_STATE="$(mktemp -d -t bfpv-state.XXXXXX)"
  export CLAUDE_PLUGIN_ROOT="$REPO_ROOT"
  export CLAUDE_CONFIG_DIR="$REPO_ROOT"
  export CLAUDE_METRICS_DIR="$TMP_METRICS"
  export CLAUDE_STATE_DIR="$TMP_STATE"
  export CLAUDE_BUGFIX_VALIDATOR_MODE="strict"
  SID="sess-gg-test"
  JSONL="$TMP_METRICS/$SID/bug-fixed-payload.jsonl"
  # BUG_FIXED with a rejected shape (env_only) — strict mode blocks (exit 2)
  # when the gate actually evaluates it. Used to prove PAIR truly no-ops.
  PAYLOAD='{"subagent_type":"software-engineer","session_id":"'"$SID"'","cwd":"/tmp","stop_hook_active":false,"transcript":"verdict: BUG_FIXED\nDEBUG_RESOLVED_VIA=env-only\n"}'
}

teardown() {
  rm -rf "$TMP_METRICS" "$TMP_STATE"
}

_run_hook_with_gear() {
  local gear="$1"
  printf '%s\n' "$gear" > "$TMP_STATE/gear-${SID}"
  run bash -c 'printf "%s" "$1" | bash "$2"' _ "$PAYLOAD" "$HOOK"
}

@test "baseline: rejected shape blocks (exit 2) in strict mode with no gear state" {
  run bash -c 'printf "%s" "$1" | bash "$2"' _ "$PAYLOAD" "$HOOK"
  [ "$status" -eq 2 ]
}

@test "GG1 gear=PAIR -> hook no-ops (exit 0, no JSONL written)" {
  _run_hook_with_gear "PAIR"
  [ "$status" -eq 0 ]
  [ ! -f "$JSONL" ]
}

@test "GG2 gear=BUILD -> hook still runs (blocks exit 2 on rejected shape)" {
  _run_hook_with_gear "BUILD"
  [ "$status" -eq 2 ]
}

@test "GG3 gear=PIPELINE -> hook still runs (blocks exit 2 on rejected shape)" {
  _run_hook_with_gear "PIPELINE"
  [ "$status" -eq 2 ]
}

@test "GG4 gear state absent -> hook still runs (fail-safe, blocks exit 2)" {
  run bash -c 'printf "%s" "$1" | bash "$2"' _ "$PAYLOAD" "$HOOK"
  [ "$status" -eq 2 ]
}
