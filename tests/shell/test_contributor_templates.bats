#!/usr/bin/env bats
# Slice A bats tests (A6, A7) — hook template skeleton + pinning suites stay green.
#
# A6: hook-template.sh must source the standard libs, read stdin, and derive
#     session_id from JSON (NOT from env — CLAUDE_SESSION_ID is unset in hooks).
# A7: existing pinning suites (hook registration invariant, agent-table, README counts)
#     remain green after templates are present.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK_TEMPLATE="$REPO_ROOT/templates/hook-template.sh"
}

# ── A6: hook template skeleton references all required elements ───────────────

@test "A6 hook-template sources libs + reads stdin session_id" {
  # Verify the hook template contains the required skeleton elements
  grep -q "hook-profile.sh" "$HOOK_TEMPLATE"
  grep -q "check_hook_profile" "$HOOK_TEMPLATE"
  grep -q "loop-guard.sh" "$HOOK_TEMPLATE"
  grep -q "INPUT=\$(cat)" "$HOOK_TEMPLATE"
  grep -q ".session_id" "$HOOK_TEMPLATE"
  grep -q "jq" "$HOOK_TEMPLATE"
}

# ── A7: pinning suites stay green with templates present ─────────────────────

@test "A7a registration-invariant still reports 12 passed, 0 failed" {
  run bash "$REPO_ROOT/hooks/tests/test-hook-registration-invariant.sh"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q "12 passed, 0 failed"
}

@test "A7b agent-table test still passes (templates/ outside agents/)" {
  run python3 -m pytest "$REPO_ROOT/tests/test_claude_md_agent_table.py" -q \
    --tb=short 2>&1
  [ "$status" -eq 0 ]
}

@test "A7c README counts test still passes (templates/ not a skill)" {
  run python3 -m pytest \
    "$REPO_ROOT/tests/test_thinking_defaults.py" \
    -k "counts_match or readme" -q --tb=short 2>&1
  [ "$status" -eq 0 ]
}
