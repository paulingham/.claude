#!/usr/bin/env bats
# Slice B — per-language function-body limits in function-body-check.sh.
# Reconciles the wave4-K single cap (8) into tight per-language smell signals:
# Ruby 5 / TS 12, with .py/.go retaining the 8-line fallback. Source-grep ACs
# (B1-B3, B8); behavioral block-on-new ACs live in
# tests/shell/test_function_body_runtime.bats.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK="$REPO_ROOT/hooks/function-body-check.sh"
}

@test "B1: hook resolves CLAUDE_FUNCTION_LINE_LIMIT_RB with default 5" {
  grep -qE 'CLAUDE_FUNCTION_LINE_LIMIT_RB:-5' "$HOOK"
}

@test "B2: hook resolves CLAUDE_FUNCTION_LINE_LIMIT_TS with default 12" {
  grep -qE 'CLAUDE_FUNCTION_LINE_LIMIT_TS:-12' "$HOOK"
}

@test "B3: hook retains CLAUDE_FUNCTION_LINE_LIMIT default 8 for py/go fallback" {
  grep -qE 'CLAUDE_FUNCTION_LINE_LIMIT:-8' "$HOOK"
}

@test "B8: hook still uses shell default-value substitution form for the fallback" {
  grep -qE 'FUNC_LIMIT=.*:-.*8' "$HOOK"
}

@test "hook header documents function body line limit" {
  grep -qiE 'function (body|line)' "$HOOK"
}
