#!/usr/bin/env bats
# Behavioral tests for preamble_tokens field in cost-tracker.sh (Stop hook).
# These are CI-gating tests (tests/shell/*.bats).
# Mirrors setup pattern from tests/shell/test_cost_feed.bats.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK="$REPO_ROOT/hooks/cost-tracker.sh"
  TMP="$(mktemp -d -t ct_preamble.XXXXXX)"
  export HOME="$TMP"
  export CLAUDE_PLUGIN_ROOT="$REPO_ROOT"
  export CLAUDE_HOOK_PROFILE="standard"
  mkdir -p "$TMP/.claude/metrics"
  COSTS="$TMP/.claude/metrics/costs.jsonl"
  unset CLAUDE_CONFIG_DIR CLAUDE_PLUGIN_DATA
}

teardown() {
  [ -d "$TMP" ] && rm -rf "$TMP"
}

@test "T1 session_end record contains integer preamble_tokens field" {
  printf '{"stop_hook_active":false}' | bash "$HOOK"
  grep -qE '"preamble_tokens":[0-9]+' "$COSTS"
}

@test "T2 preamble_tokens is greater than zero when repo sources are resolvable" {
  printf '{"stop_hook_active":false}' | bash "$HOOK"
  local val
  val=$(grep -oE '"preamble_tokens":[0-9]+' "$COSTS" | grep -oE '[0-9]+$')
  [ -n "$val" ]
  [ "$val" -gt 0 ]
}

@test "T3 empty CLAUDE_PLUGIN_ROOT (no sources) exits 0 with preamble_tokens=0" {
  local empty_root="$TMP/empty"
  mkdir -p "$empty_root/hooks/_lib"
  # Copy required hook infrastructure so hook can run at all
  cp -r "$REPO_ROOT/hooks/_lib" "$empty_root/hooks/"
  cp "$REPO_ROOT/hooks/hook-profile.sh" "$empty_root/hooks/"
  export CLAUDE_PLUGIN_ROOT="$empty_root"
  run bash -c "printf '{\"stop_hook_active\":false}' | bash '$HOOK'"
  [ "$status" -eq 0 ]
  # Exactly one session_end record
  local count
  count=$(grep -c '"event":"session_end"' "$COSTS" 2>/dev/null || echo 0)
  [ "$count" -eq 1 ]
  grep -qE '"preamble_tokens":0' "$COSTS"
}

@test "T4 helper forced failure exits 0 and emits record with preamble_tokens=0" {
  # Build an isolated root with the preamble helper non-executable in the COPY.
  # This proves the bash-level (|| echo 0) fallback fires without ever touching
  # the tracked $REPO_ROOT/hooks/_lib/preamble-tokens-emit.py.
  local isolated_root="$TMP/isolated_t4"
  mkdir -p "$isolated_root/hooks"
  cp -r "$REPO_ROOT/hooks/_lib" "$isolated_root/hooks/"
  cp "$REPO_ROOT/hooks/hook-profile.sh" "$isolated_root/hooks/"
  chmod -x "$isolated_root/hooks/_lib/preamble-tokens-emit.py"
  export CLAUDE_PLUGIN_ROOT="$isolated_root"
  run bash -c "printf '{\"stop_hook_active\":false}' | bash '$HOOK'"
  [ "$status" -eq 0 ]
  grep -qE '"preamble_tokens":0' "$COSTS"
}

@test "T5 doc-guard: cost-tracker.sh references \$preamble and helper file exists" {
  grep -q '\$preamble' "$REPO_ROOT/hooks/cost-tracker.sh"
  [ -f "$REPO_ROOT/hooks/_lib/preamble-tokens-emit.py" ]
}
