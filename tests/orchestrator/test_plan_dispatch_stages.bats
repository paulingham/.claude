#!/usr/bin/env bats
# Slice D — AC D1, D2: Stage 0 cache lookup precedes Stage 1 recon;
# H3 anchors are contiguous Stage 0,1,2,3 in file order.
# Plan: pipeline-state/plan-cache-agentic/plan.md § Slice slice-d-orchestrator-wiring.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  DOC="$REPO_ROOT/orchestrator/parallel-dispatch-details.md"
}

@test "D1 Stage 0 cache lookup precedes Stage 1 recon" {
  stage0_line="$(grep -n '^### Stage 0:' "$DOC" | head -1 | cut -d: -f1)"
  stage1_line="$(grep -n '^### Stage 1:' "$DOC" | head -1 | cut -d: -f1)"
  [ -n "$stage0_line" ]
  [ -n "$stage1_line" ]
  [ "$stage0_line" -lt "$stage1_line" ]
}

@test "D1b Stage 0 H3 mentions plan-cache lookup" {
  run grep -E '^### Stage 0:.*([Cc]ache|[Ll]ookup)' "$DOC"
  [ "$status" -eq 0 ]
}

@test "D2 H3 anchors are contiguous Stage 0,1,2,3 in file order" {
  seq="$(grep -nE '^### Stage [0-9]+:' "$DOC" | awk -F'Stage ' '{print $2}' | awk -F':' '{print $1}' | tr '\n' ',' | sed 's/,$//')"
  [ "$seq" = "0,1,2,3" ]
}

@test "D2b Stage 2 (renumbered from former Stage 1) hosts recon" {
  run grep -E '^### Stage 2:.*[Rr]econ' "$DOC"
  [ "$status" -eq 0 ]
}

@test "D2c Stage 3 (renumbered from former Stage 2) hosts architect dispatch" {
  run grep -E '^### Stage 3:.*[Aa]rchitect' "$DOC"
  [ "$status" -eq 0 ]
}
