#!/usr/bin/env bats
# Slice B — AC B4: PLAN_CACHE_MISS row in protocols/verdict-catalog.md.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  CATALOG="$REPO_ROOT/protocols/verdict-catalog.md"
}

@test "B4 PLAN_CACHE_MISS row present with polarity=info" {
  # Match by column structure to lock format: phase=plan, emitter=plan-cache-lookup.
  grep -E "\| \`PLAN_CACHE_MISS\` \| info \| \`plan-cache-lookup\` \| plan \|" "$CATALOG"
}

@test "C6 PLAN_CACHE_HIT row present with polarity=info" {
  grep -E "\| \`PLAN_CACHE_HIT\` \| info \| \`plan-cache-lookup\` \| plan \|" "$CATALOG"
}

@test "G8a ROLLOUT_GATE_PASS row present, emitter=plan-cache-rollout-gate, phase=utility" {
  grep -E "\| \`ROLLOUT_GATE_PASS\` \| success \| \`plan-cache-rollout-gate\` \| utility \|" "$CATALOG"
}

@test "G8b ROLLOUT_GATE_FAIL row present, emitter=plan-cache-rollout-gate, phase=utility" {
  grep -E "\| \`ROLLOUT_GATE_FAIL\` \| failure \| \`plan-cache-rollout-gate\` \| utility \|" "$CATALOG"
}

@test "G8c INSUFFICIENT_DATA row present for plan-cache-rollout-gate emitter" {
  # The verdict NAME already exists for eval-model-effectiveness (line ~101);
  # we add a SECOND row for plan-cache-rollout-gate per the shared-emitter
  # pattern documented in protocols/verdict-catalog.md § Notes.
  grep -E "\| \`INSUFFICIENT_DATA\` \| info \| \`plan-cache-rollout-gate\` \| utility \|" "$CATALOG"
}
