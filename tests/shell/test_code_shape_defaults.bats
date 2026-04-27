#!/usr/bin/env bats
# Cycle 1 — wave4-K-line-cap. Runtime enforcement: function-body-check.sh
# resolves CLAUDE_FUNCTION_LINE_LIMIT with a default of 8 (the canonical
# function body line cap per rules/engineering-protocol.md).

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK="$REPO_ROOT/hooks/function-body-check.sh"
}

@test "FUNC_LIMIT default is 8 in function-body-check.sh" {
  grep -qE 'CLAUDE_FUNCTION_LINE_LIMIT:-8' "$HOOK"
}

@test "hook source uses shell default-value substitution form (:-8)" {
  grep -qE 'FUNC_LIMIT=.*:-.*8' "$HOOK"
}

@test "hook header documents prose-convention canonical source" {
  # The hook is the runtime enforcement; the canonical prose source is
  # rules/engineering-protocol.md. The hook description references the
  # function-body line limit explicitly.
  grep -qiE 'function (body|line)' "$HOOK"
}
