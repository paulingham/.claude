#!/usr/bin/env bats
# Slice B — plan-cache-lookup MISS-only ACs B1, B2, B3, B5.
# Plan: pipeline-state/plan-cache-agentic/plan.md § Slice slice-b-skill-miss-only.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  LIB="$REPO_ROOT/hooks/_lib/plan-cache-lookup.sh"
  TMP_DIR="$(mktemp -d -t plan-cache-lookup-XXXXXX)"
  _PRIOR_PWD="$PWD"
  cd "$TMP_DIR"
  git init -q -b main .
  git config user.email t@e.com
  git config user.name t
  mkdir -p src pipeline-state/demo-task learning/test-xyz/plans
  printf 'task_id: demo-task\ntier: T5\ntask_class: feature\ncritical: false\n' \
    > pipeline-state/demo-task/intake.md
  printf 'doc\n' >CLAUDE.md
  printf 'src\n' >src/a.txt
  git add -A
  git commit -q -m init
  # Slice-B-required env: mode resolver MUST default to off per AC B6.
  unset CLAUDE_PLAN_CACHE_MODE
  export CLAUDE_PROJECT_HASH=test-xyz
  export HOME="$TMP_DIR"   # so default learning/ resolution is rooted under tmp
}

teardown() {
  cd "$_PRIOR_PWD"
  rm -rf "$TMP_DIR"
}

# B1 — MISS verdict + reason=no-template when no template file exists at the
# resolved cache path. Mode=shadow forces lookup (off would short-circuit).
@test "B1 MISS with reason=no-template when key absent" {
  export CLAUDE_PLAN_CACHE_MODE=shadow
  # shellcheck source=/dev/null
  source "$LIB"
  run _plan_cache_lookup demo-task feature T5 false
  [ "$status" -eq 0 ]
  [[ "$output" == *'"verdict":"PLAN_CACHE_MISS"'* ]]
  [[ "$output" == *'"reason":"no-template"'* ]]
}

# B2 — cache directory resolves under CLAUDE_PROJECT_HASH (env-first).
@test "B2 cache directory resolves under CLAUDE_PROJECT_HASH" {
  export CLAUDE_PROJECT_HASH=test-xyz
  # shellcheck source=/dev/null
  source "$LIB"
  run _plan_cache_dir
  [ "$status" -eq 0 ]
  [[ "$output" == *"learning/test-xyz/plans"* ]]
}

# B3 — fallback to _project_hash --fallback when env is unset.
@test "B3 cache directory falls back to project-hash helper" {
  unset CLAUDE_PROJECT_HASH
  # shellcheck source=/dev/null
  source "$LIB"
  run _plan_cache_dir
  [ "$status" -eq 0 ]
  # _project_hash --fallback returns a non-empty token derived from the cwd basename
  [[ "$output" == *"learning/"* ]]
  [[ "$output" == *"/plans"* ]]
  [[ "$output" != *"learning//plans"* ]]
}

# B5 — lookup uses _psp_find_active_pipelines canonical reader, not bare [ -f ].
# Contract: the skill body and the lookup helper MUST reference the union helper.
@test "B5 skill uses pipeline-state union helper" {
  SKILL="$REPO_ROOT/skills/plan-cache-lookup/SKILL.md"
  grep -q "_psp_find_active_pipelines" "$SKILL"
  grep -q "_psp_find_active_pipelines" "$LIB"
}
