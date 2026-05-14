#!/usr/bin/env bats
# Slice B — AC B4: PLAN_CACHE_MISS row in rules/verdict-catalog.md.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  CATALOG="$REPO_ROOT/rules/verdict-catalog.md"
}

@test "B4 PLAN_CACHE_MISS row present with polarity=info" {
  # Match by column structure to lock format: phase=plan, emitter=plan-cache-lookup.
  grep -E "\| \`PLAN_CACHE_MISS\` \| info \| \`plan-cache-lookup\` \| plan \|" "$CATALOG"
}

@test "C6 PLAN_CACHE_HIT row present with polarity=info" {
  grep -E "\| \`PLAN_CACHE_HIT\` \| info \| \`plan-cache-lookup\` \| plan \|" "$CATALOG"
}
