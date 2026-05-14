#!/usr/bin/env bats
# Slice: build-iter-loop-reveal
# AC5: iteration-cap tokens present in Step 4b (load-bearing identifiers
# `iteration_index` AND `MAX_ITER`); exhaustion verdict + reason pinned in 4c.

setup() {
  REPO_ROOT="$(cd "${BATS_TEST_DIRNAME}/../../.." && pwd)"
  SKILL_PATH="$REPO_ROOT/skills/build-implementation/SKILL.md"
  [ -f "$SKILL_PATH" ]
}

@test "AC5: iteration cap tokens present in Step 4b" {
  block="$(awk '/^### Step 4b/,/^### Step 4c/' "$SKILL_PATH")"
  grep -q 'iteration_index' <<<"$block"
  grep -q 'MAX_ITER' <<<"$block"
}

@test "AC5: exhaustion verdict + reason pinned in Step 4c" {
  block="$(awk '/^### Step 4c/,/^## Step 5/' "$SKILL_PATH")"
  grep -q 'BUILD_FAILED' <<<"$block"
  grep -q 'reason: iteration_cap_exhausted' <<<"$block"
}
