#!/usr/bin/env bats
# Slice F — AC F6: skill emits exact status-line strings per mode/verdict.
# Plan: pipeline-state/plan-cache-agentic/plan.md § Status Line Copy.
#
# Verbatim strings (the slice-e audit hook keys off the JSON marker; these
# console lines are the user-facing one-liners that ride alongside it).

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  LIB="$REPO_ROOT/hooks/_lib/plan-cache-lookup.sh"
  SKILL="$REPO_ROOT/skills/plan-cache-lookup/SKILL.md"
  TMP_DIR="$(mktemp -d -t plan-cache-status-XXXXXX)"
  _PRIOR_PWD="$PWD"
  cd "$TMP_DIR"
  git init -q -b main .
  git config user.email t@e.com; git config user.name t
  mkdir -p src pipeline-state/demo-task learning/test-xyz/plans
  printf 'doc\n' >CLAUDE.md; printf 'src\n' >src/a.txt
  git add -A; git commit -q -m init
  export CLAUDE_PROJECT_HASH=test-xyz
  export HOME="$TMP_DIR"
  unset CLAUDE_PLAN_CACHE_MODE
}

teardown() {
  cd "$_PRIOR_PWD"
  rm -rf "$TMP_DIR"
}

@test "F6 shadow-mode MISS emits verbatim status line" {
  export CLAUDE_PLAN_CACHE_MODE=shadow
  # shellcheck source=/dev/null
  source "$LIB"
  local rh key dir
  rh=$(_repo_hash); key=$(_plan_cache_key feature "$rh" T5 false); dir=$(_plan_cache_dir)
  mkdir -p "$dir"; printf 'stub\n' >"$dir/$key.md"
  run _plan_cache_lookup feature T5 false
  [ "$status" -eq 0 ]
  [[ "$output" == *'[plan-cache] shadow-mode active (cache observable, not serving) — recon+architect running as normal'* ]]
}

@test "F6b no-template MISS emits verbatim status line" {
  export CLAUDE_PLAN_CACHE_MODE=shadow
  # shellcheck source=/dev/null
  source "$LIB"
  run _plan_cache_lookup feature T5 false
  [ "$status" -eq 0 ]
  [[ "$output" == *'[plan-cache] no cached plan for this task signature — recon+architect running as normal'* ]]
}

@test "F6c disabled MISS is silent (no status line emitted)" {
  export CLAUDE_PLAN_CACHE_MODE=off
  # shellcheck source=/dev/null
  source "$LIB"
  run _plan_cache_lookup feature T5 false
  [ "$status" -eq 0 ]
  # JSON marker is still emitted for audit; the human-readable status line is NOT.
  [[ "$output" == *'"reason":"disabled"'* ]]
  ! [[ "$output" == *'[plan-cache] '* ]] || {
    # Permit the JSON marker prefix '[PlanCacheLookup]' but reject any
    # '[plan-cache] '-prefixed human line per plan.md § Status Line Copy.
    ! printf '%s\n' "$output" | grep -qE '^\[plan-cache\] '
  }
}

@test "F6d HIT emits verbatim status line (with placeholders interpolated)" {
  export CLAUDE_PLAN_CACHE_MODE=on
  # shellcheck source=/dev/null
  source "$LIB"
  local rh key dir tmpl plan
  rh=$(_repo_hash); key=$(_plan_cache_key feature "$rh" T5 false); dir=$(_plan_cache_dir)
  tmpl="$dir/$key.md"; plan="pipeline-state/demo-task/plan.md"
  mkdir -p "$(dirname "$plan")"
  printf -- '---\nlast_adapt_outcome: null\n---\n' >"$tmpl"
  cat >"$plan" <<'EOF'
---
cache_hit: true
---
## Slices
## Alternatives Considered
## Codebase Ground-Truth Citations
## Pre-Mortem
EOF
  CLAUDE_PLAN_CACHE_ADAPT_SECS=4 CLAUDE_PLAN_CACHE_SAVINGS_USD=0.014 \
    run _plan_cache_finalize "$tmpl" "$plan" "$key"
  [ "$status" -eq 0 ]
  [[ "$output" == *'[plan-cache] cache HIT — Haiku adapted in 4s, estimated savings ~$0.014; verify slices against current repo before Build'* ]]
}

@test "F6e adapter-rejected MISS emits verbatim status line" {
  export CLAUDE_PLAN_CACHE_MODE=on
  # shellcheck source=/dev/null
  source "$LIB"
  local rh key dir tmpl plan
  rh=$(_repo_hash); key=$(_plan_cache_key feature "$rh" T5 false); dir=$(_plan_cache_dir)
  tmpl="$dir/$key.md"; plan="pipeline-state/demo-task/plan.md"
  mkdir -p "$(dirname "$plan")"
  printf -- '---\nlast_adapt_outcome: pending\n---\n' >"$tmpl"
  # invalid plan (missing required sections) → validator rejects
  printf 'not a valid plan\n' >"$plan"
  run _plan_cache_finalize "$tmpl" "$plan" "$key"
  [ "$status" -eq 0 ]
  [[ "$output" == *'[plan-cache] adapter output rejected by validator — falling through to recon+architect in this pipeline (Iron Law 6)'* ]]
}

@test "F6f SKILL.md documents the Status Line Copy verbatim" {
  # Documentation ratchet: the verbatim strings live in plan.md § Status Line
  # Copy. SKILL.md must mirror them so consumers don't drift from the contract.
  grep -qF 'shadow-mode active (cache observable, not serving) — recon+architect running as normal' "$SKILL"
  grep -qF 'no cached plan for this task signature — recon+architect running as normal' "$SKILL"
  grep -qF 'cache HIT — Haiku adapted in' "$SKILL"
  grep -qF 'adapter output rejected by validator — falling through to recon+architect in this pipeline (Iron Law 6)' "$SKILL"
}
