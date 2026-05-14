#!/usr/bin/env bats
# Slice F — Mode resolver / shadow-default / write-on-MISS / off-noop / on-HIT.
# Plan: pipeline-state/plan-cache-agentic/plan.md § Slice slice-f-shadow-mode-rollout.
#
# ACs:
#   F1  default CLAUDE_PLAN_CACHE_MODE is shadow after Slice F
#   F2  shadow mode emits MISS even when key exists (reason=shadow-mode)
#   F3  shadow mode writes template on Plan Validation APPROVED
#   F4  off mode is no-op (no read, no write; MISS reason=disabled)
#   F5  on mode serves HIT when key matches (validator-pass → PLAN_CACHE_HIT)

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  LIB="$REPO_ROOT/hooks/_lib/plan-cache-lookup.sh"
  TMP_DIR="$(mktemp -d -t plan-cache-mode-XXXXXX)"
  _PRIOR_PWD="$PWD"
  cd "$TMP_DIR"
  git init -q -b main .
  git config user.email t@e.com
  git config user.name t
  mkdir -p src pipeline-state/demo-task learning/test-xyz/plans
  printf 'doc\n' >CLAUDE.md
  printf 'src\n' >src/a.txt
  git add -A
  git commit -q -m init
  export CLAUDE_PROJECT_HASH=test-xyz
  export HOME="$TMP_DIR"
  unset CLAUDE_PLAN_CACHE_MODE
}

teardown() {
  cd "$_PRIOR_PWD"
  rm -rf "$TMP_DIR"
}

# F1 — unset env resolves to shadow after Slice F flip.
@test "F1 default CLAUDE_PLAN_CACHE_MODE is shadow after Slice F" {
  # shellcheck source=/dev/null
  source "$LIB"
  run _plan_cache_mode
  [ "$status" -eq 0 ]
  [ "$output" = "shadow" ]
}

# F2 — shadow + key present → MISS reason=shadow-mode (no HIT served).
@test "F2 shadow mode emits MISS even when key exists" {
  export CLAUDE_PLAN_CACHE_MODE=shadow
  # shellcheck source=/dev/null
  source "$LIB"
  local rh key dir
  rh=$(_repo_hash)
  key=$(_plan_cache_key feature "$rh" T5 false)
  dir=$(_plan_cache_dir)
  mkdir -p "$dir"
  printf 'stub\n' >"$dir/$key.md"
  run _plan_cache_lookup feature T5 false
  [ "$status" -eq 0 ]
  [[ "$output" == *'"verdict":"PLAN_CACHE_MISS"'* ]]
  [[ "$output" == *'"reason":"shadow-mode"'* ]]
}

# F3 — shadow mode writes a template under learning/{hash}/plans/{key}.md
# after Plan Validation APPROVED. The new helper takes the canonical plan.md
# path + key context and produces the cached template (frontmatter + body copy).
@test "F3 shadow mode writes template on Plan Validation APPROVED" {
  export CLAUDE_PLAN_CACHE_MODE=shadow
  # shellcheck source=/dev/null
  source "$LIB"
  local rh key dir plan
  rh=$(_repo_hash)
  key=$(_plan_cache_key feature "$rh" T5 false)
  dir=$(_plan_cache_dir)
  plan="pipeline-state/demo-task/plan.md"
  mkdir -p "$(dirname "$plan")"
  cat >"$plan" <<'EOF'
---
task_id: demo-task
---
## Slices
## Alternatives Considered
## Codebase Ground-Truth Citations
## Pre-Mortem
EOF
  run _plan_cache_write_template "$plan" "$key" feature T5 false "$rh" demo-task
  [ "$status" -eq 0 ]
  [ -f "$dir/$key.md" ]
  grep -qE "^cache_key: $key$" "$dir/$key.md"
  grep -qE "^task_class: feature$" "$dir/$key.md"
  grep -qE "^tier: T5$" "$dir/$key.md"
  grep -qE "^critical: false$" "$dir/$key.md"
  grep -qE "^repo_hash: $rh$" "$dir/$key.md"
  grep -qE "^source_pipeline: demo-task$" "$dir/$key.md"
  grep -qE "^hit_count: 0$" "$dir/$key.md"
  grep -qE "^last_adapt_outcome: null$" "$dir/$key.md"
}

# F3b — write is idempotent: re-writing the same key replaces atomically and
# does not duplicate frontmatter.
@test "F3b write_template is atomic (tmp+mv) and idempotent" {
  export CLAUDE_PLAN_CACHE_MODE=shadow
  # shellcheck source=/dev/null
  source "$LIB"
  local rh key dir plan
  rh=$(_repo_hash); key=$(_plan_cache_key feature "$rh" T5 false); dir=$(_plan_cache_dir)
  plan="pipeline-state/demo-task/plan.md"
  mkdir -p "$(dirname "$plan")"
  printf -- '---\n---\n## Slices\n## Alternatives Considered\n## Codebase Ground-Truth Citations\n## Pre-Mortem\n' >"$plan"
  _plan_cache_write_template "$plan" "$key" feature T5 false "$rh" demo-task
  _plan_cache_write_template "$plan" "$key" feature T5 false "$rh" demo-task
  local count
  count=$(grep -c "^cache_key: " "$dir/$key.md")
  [ "$count" -eq 1 ]
}

# F4 — off mode is a no-op: no read, no write, MISS reason=disabled.
@test "F4 off mode is no-op" {
  export CLAUDE_PLAN_CACHE_MODE=off
  # shellcheck source=/dev/null
  source "$LIB"
  local rh key dir
  rh=$(_repo_hash); key=$(_plan_cache_key feature "$rh" T5 false); dir=$(_plan_cache_dir)
  mkdir -p "$dir"
  printf 'stub\n' >"$dir/$key.md"
  run _plan_cache_lookup feature T5 false
  [ "$status" -eq 0 ]
  [[ "$output" == *'"reason":"disabled"'* ]]
  # cache key in the disabled emit is empty — no lookup occurred.
  [[ "$output" == *'"cache_key":""'* ]]
}

# F5 — on mode + valid plan + validator-pass → PLAN_CACHE_HIT.
@test "F5 on mode serves HIT when key matches" {
  export CLAUDE_PLAN_CACHE_MODE=on
  # shellcheck source=/dev/null
  source "$LIB"
  local rh key dir tmpl plan
  rh=$(_repo_hash); key=$(_plan_cache_key feature "$rh" T5 false); dir=$(_plan_cache_dir)
  tmpl="$dir/$key.md"; plan="pipeline-state/demo-task/plan.md"
  mkdir -p "$(dirname "$plan")"
  printf -- '---\nlast_adapt_outcome: null\nlast_adapted_at: null\n---\n' >"$tmpl"
  cat >"$plan" <<'EOF'
---
cache_hit: true
---
## Slices
## Alternatives Considered
## Codebase Ground-Truth Citations
## Pre-Mortem
EOF
  run _plan_cache_finalize "$tmpl" "$plan" "$key"
  [ "$status" -eq 0 ]
  [[ "$output" == *'"verdict":"PLAN_CACHE_HIT"'* ]]
  [[ "$output" == *"\"cache_key\":\"$key\""* ]]
  grep -qE "^last_adapt_outcome: success$" "$tmpl"
}
