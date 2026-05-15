#!/usr/bin/env bats
# Slice C — AC C2: structural validator rejects plan missing required section.
# Plan: pipeline-state/plan-cache-agentic/plan.md § Slice slice-c-adapter-and-validator.
#
# Required sections (validator failure on any missing):
#   ## Slices
#   ## Alternatives Considered
#   ## Codebase Ground-Truth Citations
#   ## Pre-Mortem
# Plus the `cache_hit: true` marker in the frontmatter / body.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  LIB="$REPO_ROOT/hooks/_lib/plan-cache-lookup.sh"
  TMP_DIR="$(mktemp -d -t plan-cache-validator-XXXXXX)"
  _PRIOR_PWD="$PWD"
  cd "$TMP_DIR"
  source "$LIB"
}

teardown() {
  cd "$_PRIOR_PWD"
  rm -rf "$TMP_DIR"
}

# C2 — Missing `## Slices` → validator returns non-zero.
@test "C2 validator rejects plan missing ## Slices" {
  PLAN="$TMP_DIR/plan.md"
  cat >"$PLAN" <<EOF
---
cache_hit: true
---
## Alternatives Considered
## Codebase Ground-Truth Citations
## Pre-Mortem
no slices section
EOF
  run _plan_cache_validate_plan "$PLAN"
  [ "$status" -ne 0 ]
}

@test "C2b validator rejects plan missing ## Alternatives Considered" {
  PLAN="$TMP_DIR/plan.md"
  cat >"$PLAN" <<EOF
---
cache_hit: true
---
## Slices
## Codebase Ground-Truth Citations
## Pre-Mortem
EOF
  run _plan_cache_validate_plan "$PLAN"
  [ "$status" -ne 0 ]
}

@test "C2c validator rejects plan missing ## Codebase Ground-Truth Citations" {
  PLAN="$TMP_DIR/plan.md"
  cat >"$PLAN" <<EOF
---
cache_hit: true
---
## Slices
## Alternatives Considered
## Pre-Mortem
EOF
  run _plan_cache_validate_plan "$PLAN"
  [ "$status" -ne 0 ]
}

@test "C2d validator rejects plan missing ## Pre-Mortem" {
  PLAN="$TMP_DIR/plan.md"
  cat >"$PLAN" <<EOF
---
cache_hit: true
---
## Slices
## Alternatives Considered
## Codebase Ground-Truth Citations
EOF
  run _plan_cache_validate_plan "$PLAN"
  [ "$status" -ne 0 ]
}

@test "C2e validator accepts plan with all four sections + cache_hit marker" {
  PLAN="$TMP_DIR/plan.md"
  cat >"$PLAN" <<EOF
---
cache_hit: true
---
## Slices
## Alternatives Considered
## Codebase Ground-Truth Citations
## Pre-Mortem
EOF
  run _plan_cache_validate_plan "$PLAN"
  [ "$status" -eq 0 ]
}
