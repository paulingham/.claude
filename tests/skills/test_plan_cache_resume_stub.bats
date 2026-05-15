#!/usr/bin/env bats
# Slice C — AC C8: HIT path writes stub architect-context.md before adapter spawn.
# Plan: pipeline-state/plan-cache-agentic/plan.md § Slice slice-c-adapter-and-validator.
#
# Resume-safety: if a pipeline is interrupted mid-HIT-path, /pipeline-resume
# must find architect-context.md (recon Stage 1 output) so resume readers don't
# stall on the missing-file condition. Stub body documents that recon was
# skipped because of cache hit.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  LIB="$REPO_ROOT/hooks/_lib/plan-cache-lookup.sh"
  TMP_DIR="$(mktemp -d -t plan-cache-resume-XXXXXX)"
  _PRIOR_PWD="$PWD"
  cd "$TMP_DIR"
  mkdir -p pipeline-state/demo-task
  source "$LIB"
}

teardown() {
  cd "$_PRIOR_PWD"
  rm -rf "$TMP_DIR"
}

# C8 — stub file created at the expected path with the documented body.
@test "C8 HIT path writes stub architect-context.md before adapter spawn" {
  _plan_cache_write_resume_stub demo-task
  STUB="$TMP_DIR/pipeline-state/demo-task/architect-context.md"
  [ -f "$STUB" ]
  grep -qF '<!-- cache_hit: true, recon-skipped -->' "$STUB"
}

# Idempotent: re-running on the same task_id does not error.
@test "C8b stub write is idempotent" {
  _plan_cache_write_resume_stub demo-task
  run _plan_cache_write_resume_stub demo-task
  [ "$status" -eq 0 ]
  STUB="$TMP_DIR/pipeline-state/demo-task/architect-context.md"
  # File still contains the marker (no duplication / corruption).
  grep -qF '<!-- cache_hit: true, recon-skipped -->' "$STUB"
}
