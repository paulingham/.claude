#!/usr/bin/env bats
# Slice: build-iter-loop-reveal
# AC2: CLAUDE_BUILD_ITERATIONS env-var contract — default 3 read site,
# =0 documented as disable hatch, bound-check idiom enforces 0..10.

setup() {
  REPO_ROOT="$(cd "${BATS_TEST_DIRNAME}/../../.." && pwd)"
  SKILL_PATH="$REPO_ROOT/skills/build-implementation/SKILL.md"
  [ -f "$SKILL_PATH" ]
}

@test "AC2: CLAUDE_BUILD_ITERATIONS default 3 read site" {
  grep -q 'CLAUDE_BUILD_ITERATIONS:-3' "$SKILL_PATH"
}

@test "AC2: =0 documented as disable hatch (co-located within 10 lines)" {
  awk '/CLAUDE_BUILD_ITERATIONS=0/{found=NR}
       found && NR>=found && NR<=found+10 && /disables|SKIPS/{print; exit}' \
      "$SKILL_PATH" | grep -qE 'disables|SKIPS'
}

@test "AC2: bound-check idiom enforces 0..10 inside Step 4c block" {
  block="$(awk '/^### Step 4c/,/^## Step 5/' "$SKILL_PATH")"
  grep -q 'case "\$MAX_ITER" in' <<<"$block"
  grep -q '\*\[!0-9\]\*' <<<"$block"
  grep -q 'MAX_ITER > 10' <<<"$block"
}
