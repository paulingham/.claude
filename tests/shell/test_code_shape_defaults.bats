#!/usr/bin/env bats
# Cycle 1 — wave4-K-line-cap. Documentation-as-code: hook source declares
# FUNCTION_LINE_LIMIT default of 8 (prose-convention enforcement, not runtime).

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK="$REPO_ROOT/hooks/code-shape-check.sh"
}

@test "FUNCTION_LINE_LIMIT default is 8 in hook source" {
  grep -qE 'CLAUDE_FUNCTION_LINE_LIMIT[^}]*8[^}]*\}' "$HOOK" \
    || grep -qE 'FUNCTION_LINE_LIMIT=.*8' "$HOOK"
}

@test "hook source uses shell default-value substitution form" {
  grep -qE 'FUNCTION_LINE_LIMIT.*:-.*8' "$HOOK"
}

@test "hook comment states function-level enforcement is via prose convention" {
  grep -q "prose convention" "$HOOK"
}
