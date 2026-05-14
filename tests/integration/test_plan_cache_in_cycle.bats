#!/usr/bin/env bats
# Slice C — AC C7 (HIGH-prod-2 two-observable): adapter-rejected in-cycle fallthrough.
# Plan: pipeline-state/plan-cache-agentic/plan.md § Slice slice-c-adapter-and-validator.
#
# Two observables in ONE bats test:
#   (a) metrics/{session}/plan-cache.jsonl contains BOTH
#       - verdict=PLAN_CACHE_MISS reason=adapter-rejected session_id=X
#       - PLAN_CACHE_FALLTHROUGH session_id=X reason=adapter-rejected
#   (b) grep -rE 'next_attempt|deferred|retry_on_next_pipeline'
#       pipeline-state/{task-id}/ returns 0 matches across *.md, *.json, *.yaml.
#
# Iron Law 6: in-cycle remediation. NO follow-up. NO deferral tokens.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  LIB="$REPO_ROOT/hooks/_lib/plan-cache-lookup.sh"
  TMP_DIR="$(mktemp -d -t plan-cache-in-cycle-XXXXXX)"
  _PRIOR_PWD="$PWD"
  cd "$TMP_DIR"
  git init -q -b main .
  git config user.email t@e.com
  git config user.name t
  mkdir -p src pipeline-state/demo-task learning/test-xyz/plans
  printf 'task_id: demo-task\n' >pipeline-state/demo-task/intake.md
  printf 'doc\n' >CLAUDE.md
  printf 'src\n' >src/a.txt
  git add -A
  git commit -q -m init
  export CLAUDE_PROJECT_HASH=test-xyz
  export HOME="$TMP_DIR"
  export CLAUDE_SESSION_ID=test-session-c7
  export CLAUDE_PLAN_CACHE_MODE=on
  source "$LIB"
  KEY=$(_plan_cache_key feature "$(_repo_hash)" T5 false)
  TEMPLATE="$TMP_DIR/learning/test-xyz/plans/$KEY.md"
  cat >"$TEMPLATE" <<EOF
---
cache_key: $KEY
task_class: feature
tier: T5
critical: false
repo_hash: abc
created_at: 2026-05-01T00:00:00Z
hit_count: 0
last_adapted_at: null
last_adapt_outcome: null
source_pipeline: prior-task
---
EOF
}

teardown() {
  cd "$_PRIOR_PWD"
  rm -rf "$TMP_DIR"
}

# C7 — two observables (forensics JSONL pair + zero deferral tokens) in one test.
@test "C7 adapter-rejected: MISS line + FALLTHROUGH trace + zero deferral tokens" {
  PLAN_FILE="$TMP_DIR/pipeline-state/demo-task/plan.md"
  # Simulate an adapter that produced a structurally-invalid plan.
  printf 'rejected plan, missing required sections\n' >"$PLAN_FILE"

  _plan_cache_write_pending "$TEMPLATE"
  run _plan_cache_finalize "$TEMPLATE" "$PLAN_FILE" "$KEY"
  [ "$status" -eq 0 ]

  # Observable (a): both JSONL lines present in the session file.
  JSONL="$TMP_DIR/metrics/test-session-c7/plan-cache.jsonl"
  [ -f "$JSONL" ]
  grep -qE '"verdict":"PLAN_CACHE_MISS".*"reason":"adapter-rejected".*"session_id":"test-session-c7"' "$JSONL"
  grep -qE '"event":"PLAN_CACHE_FALLTHROUGH".*"session_id":"test-session-c7".*"reason":"adapter-rejected"' "$JSONL"

  # Observable (b): zero deferral tokens in pipeline-state/{task-id}/.
  run grep -rE 'next_attempt|deferred|retry_on_next_pipeline' \
    "$TMP_DIR/pipeline-state/demo-task/" --include='*.md' --include='*.json' --include='*.yaml'
  [ "$status" -ne 0 ]   # grep returns 1 when no matches — which is what we want.
}
