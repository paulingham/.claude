#!/usr/bin/env bats
# Slice: build-iter-loop-reveal
# AC3 + AC4: software-engineer.md and frontend-engineer.md each declare an
# `Iterative Refinement on RED (Build Phase)` section that references the
# scratchpad category test-failure-feedback.

setup() {
  REPO_ROOT="$(cd "${BATS_TEST_DIRNAME}/../../.." && pwd)"
  SWE_PATH="$REPO_ROOT/agents/software-engineer.md"
  FE_PATH="$REPO_ROOT/agents/frontend-engineer.md"
  [ -f "$SWE_PATH" ]
  [ -f "$FE_PATH" ]
}

@test "AC3: software-engineer.md has Iterative Refinement on RED section + test-failure-feedback" {
  grep -q "Iterative Refinement on RED" "$SWE_PATH"
  grep -q "test-failure-feedback" "$SWE_PATH"
}

@test "AC4: frontend-engineer.md has Iterative Refinement on RED section + test-failure-feedback" {
  grep -q "Iterative Refinement on RED" "$FE_PATH"
  grep -q "test-failure-feedback" "$FE_PATH"
}
