#!/usr/bin/env bats
# Asserts that hooks/tests/test-hook-registration-invariant.sh exits 0 with all 12 ACs passing.
# ATDD contract for Slice C3 of golden-path-convergence-hooks.
#
# (1) Registration invariant script exits 0 and reports 12 passed, 0 failed
# (2) README documents reflect-gate-acknowledgment (basename grep)
# (3) README documents reflect-token-emit (basename grep)

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
}

# ── (1) Registration invariant is fully green ─────────────────────────────────

@test "C3.1 registration-invariant exits 0 (12/12 green)" {
  run bash "$REPO_ROOT/hooks/tests/test-hook-registration-invariant.sh"
  [ "$status" -eq 0 ]
}

@test "C3.2 registration-invariant summary is 12 passed, 0 failed" {
  run bash "$REPO_ROOT/hooks/tests/test-hook-registration-invariant.sh"
  echo "$output" | grep -q "12 passed, 0 failed"
}

# ── (2) README documents the reflect hooks ────────────────────────────────────

@test "C3.3 README documents reflect-gate-acknowledgment" {
  grep -q "reflect-gate-acknowledgment" "$REPO_ROOT/README.md"
}

@test "C3.4 README documents reflect-token-emit" {
  grep -q "reflect-token-emit" "$REPO_ROOT/README.md"
}
