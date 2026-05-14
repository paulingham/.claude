#!/usr/bin/env bats
# Slice: build-iter-loop-reveal
# AC1 + AC6: Step 4a/4b/4c headings present in SKILL.md; Step 4b cites ReVeal
# (arXiv 2506.11442) inside its own block; Step 4b references scratchpad
# category test-failure-feedback; Step 4c references /bug-fix and BUILD_FAILED.

setup() {
  REPO_ROOT="$(cd "${BATS_TEST_DIRNAME}/../../.." && pwd)"
  SKILL_PATH="$REPO_ROOT/skills/build-implementation/SKILL.md"
  [ -f "$SKILL_PATH" ]
}

@test "AC1: Step 4a/4b/4c headings present" {
  grep -q '^### Step 4a' "$SKILL_PATH"
  grep -q '^### Step 4b' "$SKILL_PATH"
  grep -q '^### Step 4c' "$SKILL_PATH"
}

@test "AC1: Step 4b references scratchpad category test-failure-feedback and ReVeal" {
  block="$(awk '/^### Step 4b/,/^### Step 4c/' "$SKILL_PATH")"
  grep -q "category: test-failure-feedback" <<<"$block"
  grep -q "ReVeal" <<<"$block"
}

@test "AC1: Step 4c references /bug-fix and BUILD_FAILED" {
  block="$(awk '/^### Step 4c/,/^## Step 5/' "$SKILL_PATH")"
  grep -q "/bug-fix" <<<"$block"
  grep -q "BUILD_FAILED" <<<"$block"
}

@test "AC6: ReVeal arXiv 2506.11442 cited inside Step 4b block" {
  block="$(awk '/^### Step 4b/,/^### Step 4c/' "$SKILL_PATH")"
  grep -q 'arXiv 2506.11442' <<<"$block"
}
