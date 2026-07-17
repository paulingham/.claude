#!/usr/bin/env bats
# Slice C — plan-cache-adapter ACs C1, C3, C4, C5.
# Plan: pipeline-state/plan-cache-agentic/plan.md § Slice slice-c-adapter-and-validator.
#
# The HIT path's contract:
#   1. Skill writes last_adapted_at=now(), last_adapt_outcome=pending to the
#      cached template BEFORE the adapter spawn (state-before-expensive-op,
#      Memory M5).
#   2. Skill writes a stub architect-context.md for resume-safety (C8 — that
#      AC has its own test file).
#   3. Skill spawns the adapter (Agent tool, model=haiku); adapter writes the
#      adapted plan with `cache_hit: true` marker into pipeline-state/{task-id}/plan.md.
#   4. Skill runs structural validator. Pass → outcome=success, emit HIT.
#      Fail → DELETE plan.md, outcome=failed, emit MISS reason=adapter-rejected.
#      NO retry (Iron Law 6 — fallthrough in-cycle).
#
# These tests exercise the lib-level functions that implement steps 1, 3 (the
# finalize path), 4, and the contract assertion on the SKILL.md body (step 3).
# The real Agent spawn is documented in SKILL.md prose; tests substitute the
# adapter via PLAN_CACHE_ADAPTER_CMD (test-only injection).

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  LIB="$REPO_ROOT/hooks/_lib/plan-cache-lookup.sh"
  SKILL="$REPO_ROOT/skills/plan-cache-lookup/SKILL.md"
  TMP_DIR="$(mktemp -d -t plan-cache-adapter-XXXXXX)"
  _PRIOR_PWD="$PWD"
  cd "$TMP_DIR"
  git init -q -b main .
  git config user.email t@e.com
  git config user.name t
  mkdir -p src pipeline-state/demo-task learning/test-xyz/plans metrics/test-session
  printf 'task_id: demo-task\n' >pipeline-state/demo-task/intake.md
  printf 'doc\n' >CLAUDE.md
  printf 'src\n' >src/a.txt
  git add -A
  git commit -q -m init
  export CLAUDE_PROJECT_HASH=test-xyz
  export HOME="$TMP_DIR"
  export CLAUDE_SESSION_ID=test-session
  export CLAUDE_PLAN_CACHE_MODE=on
  # Plant a cached template with the schema documented in plan.md § Contracts Touched.
  source "$LIB"
  KEY=$(_plan_cache_key feature "$(_repo_hash)" BUILD false)
  TEMPLATE="$TMP_DIR/learning/test-xyz/plans/$KEY.md"
  cat >"$TEMPLATE" <<EOF
---
cache_key: $KEY
task_class: feature
gear: BUILD
critical: false
repo_hash: abc
created_at: 2026-05-01T00:00:00Z
hit_count: 0
last_adapted_at: null
last_adapt_outcome: null
source_pipeline: prior-task
---
# Cached plan body
EOF
}

teardown() {
  cd "$_PRIOR_PWD"
  rm -rf "$TMP_DIR"
}

# C1 — Template frontmatter mutated to outcome=pending BEFORE adapter spawn.
# If the adapter crashes, the pending marker is still there on next entry.
@test "C1 last_adapted_at written before adapter spawn" {
  _plan_cache_write_pending "$TEMPLATE"
  grep -q '^last_adapt_outcome: pending$' "$TEMPLATE"
  grep -qE '^last_adapted_at: [0-9]{4}-[0-9]{2}-[0-9]{2}T' "$TEMPLATE"
}

# C3 — Adapter rejection path: skill emits MISS reason=adapter-rejected,
# deletes the produced plan.md, and flips outcome=failed on the template.
@test "C3 adapter rejection emits MISS not HIT" {
  PLAN_FILE="$TMP_DIR/pipeline-state/demo-task/plan.md"
  printf 'no required sections here\n' >"$PLAN_FILE"
  _plan_cache_write_pending "$TEMPLATE"
  run _plan_cache_finalize "$TEMPLATE" "$PLAN_FILE" "$KEY"
  [ "$status" -eq 0 ]
  [[ "$output" == *'"verdict":"PLAN_CACHE_MISS"'* ]]
  [[ "$output" == *'"reason":"adapter-rejected"'* ]]
  [ ! -f "$PLAN_FILE" ]
  grep -q '^last_adapt_outcome: failed$' "$TEMPLATE"
}

# C4 — Contract assertion (MEDIUM-eng-1 downgrade): SKILL.md body documents
# exactly one Agent-spawn directive on the HIT path and no retry/loop construct
# in the surrounding HIT-path section. We assert by greppable directive markers
# in the doc rather than mocking the Agent tool itself.
@test "C4 skill body contains exactly one Agent-spawn directive and zero retry constructs over it" {
  # Exactly one fenced "Agent({" block in SKILL.md.
  spawn_count=$(grep -cE '^Agent\(\{' "$SKILL")
  [ "$spawn_count" -eq 1 ]
  # Extract the HIT Path Dispatch section (the section containing the Agent
  # spawn directive) and assert no loop/retry control tokens in it. The
  # surrounding context is bounded by H2 anchors so prose elsewhere in the
  # file (`for safety`, `until Slice D`, etc.) is not in scope.
  hit_section=$(awk '/^## HIT Path Dispatch/{flag=1; next} /^## /{flag=0} flag' "$SKILL")
  ! echo "$hit_section" | grep -qE '\b(for |while |until |retry)\b'
}

# C5 — Adapted plan must contain the cache_hit: true marker; validator
# rejects plans missing it.
@test "C5 adapted plan contains cache_hit: true" {
  PLAN_FILE="$TMP_DIR/pipeline-state/demo-task/plan.md"
  cat >"$PLAN_FILE" <<EOF
---
cache_hit: true
---
## Slices
## Alternatives Considered
## Codebase Ground-Truth Citations
## Pre-Mortem
body
EOF
  run _plan_cache_validate_plan "$PLAN_FILE"
  [ "$status" -eq 0 ]

  # HIT branch coverage: a valid plan returns HIT verdict + outcome=success.
  PLAN_FILE="$TMP_DIR/pipeline-state/demo-task/plan-ok.md"
  cat >"$PLAN_FILE" <<EOF
---
cache_hit: true
---
## Slices
## Alternatives Considered
## Codebase Ground-Truth Citations
## Pre-Mortem
EOF
  _plan_cache_write_pending "$TEMPLATE"
  run _plan_cache_finalize "$TEMPLATE" "$PLAN_FILE" "$KEY"
  [ "$status" -eq 0 ]
  [[ "$output" == *'"verdict":"PLAN_CACHE_HIT"'* ]]
  [ -f "$PLAN_FILE" ]
  grep -q '^last_adapt_outcome: success$' "$TEMPLATE"

  # Plan without the marker fails the validator.
  cat >"$PLAN_FILE" <<EOF
---
cache_hit: false
---
## Slices
## Alternatives Considered
## Codebase Ground-Truth Citations
## Pre-Mortem
EOF
  run _plan_cache_validate_plan "$PLAN_FILE"
  [ "$status" -ne 0 ]
}
