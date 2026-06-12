#!/usr/bin/env bats
# Asserts that the 3 dead advisory hooks and all their pinning artifacts are gone.
# ATDD contract for Slice C1 of golden-path-convergence-hooks.
#
# (1) Hook script files absent from hooks/
# (2) Zero registry refs in hooks.json and settings.json for the 3 basenames
# (3) build_loop_scan.py no longer references governance-capture
# (4) Pinning test files removed:
#     - hooks/tests/test-mutation-tooling-guard.sh absent
#     - No auto-bug-detect grep refs in state-hooks.bats or project-hash.bats

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
}

# ── (1) Hook script files absent ─────────────────────────────────────────────

@test "C1.1a hooks/governance-capture.sh is deleted" {
  [ ! -f "$REPO_ROOT/hooks/governance-capture.sh" ]
}

@test "C1.1b hooks/auto-bug-detect.sh is deleted" {
  [ ! -f "$REPO_ROOT/hooks/auto-bug-detect.sh" ]
}

@test "C1.1c hooks/mutation-tooling-guard.sh is deleted" {
  [ ! -f "$REPO_ROOT/hooks/mutation-tooling-guard.sh" ]
}

# ── (2) Zero registry refs in both JSONs ─────────────────────────────────────

@test "C1.2a hooks.json has no governance-capture reference" {
  run grep -c "governance-capture" "$REPO_ROOT/hooks/hooks.json"
  [ "$output" = "0" ]
}

@test "C1.2b hooks.json has no auto-bug-detect reference" {
  run grep -c "auto-bug-detect" "$REPO_ROOT/hooks/hooks.json"
  [ "$output" = "0" ]
}

@test "C1.2c hooks.json has no mutation-tooling-guard reference" {
  run grep -c "mutation-tooling-guard" "$REPO_ROOT/hooks/hooks.json"
  [ "$output" = "0" ]
}

@test "C1.2d settings.json has no governance-capture reference" {
  run grep -c "governance-capture" "$REPO_ROOT/settings.json"
  [ "$output" = "0" ]
}

@test "C1.2e settings.json has no auto-bug-detect reference" {
  run grep -c "auto-bug-detect" "$REPO_ROOT/settings.json"
  [ "$output" = "0" ]
}

@test "C1.2f both JSONs remain valid after removal" {
  run python3 -c "import json; json.load(open('$REPO_ROOT/hooks/hooks.json')); json.load(open('$REPO_ROOT/settings.json')); print('OK')"
  [ "$status" -eq 0 ]
  [ "$output" = "OK" ]
}

# ── (3) build_loop_scan.py no longer greps governance-capture ────────────────

@test "C1.3 build_loop_scan.py has no governance-capture reference" {
  run grep -c "governance-capture" "$REPO_ROOT/hooks/_lib/build_loop_scan.py"
  [ "$output" = "0" ]
}

# ── (4) Stale pinning tests removed ──────────────────────────────────────────

@test "C1.4a hooks/tests/test-mutation-tooling-guard.sh is deleted" {
  [ ! -f "$REPO_ROOT/hooks/tests/test-mutation-tooling-guard.sh" ]
}

@test "C1.4b state-hooks.bats has no auto-bug-detect grep reference" {
  run grep -c "auto-bug-detect" "$REPO_ROOT/tests/shell/state-hooks.bats"
  [ "$output" = "0" ]
}

@test "C1.4c project-hash.bats has no auto-bug-detect grep reference" {
  run grep -c "auto-bug-detect" "$REPO_ROOT/tests/shell/project-hash.bats"
  [ "$output" = "0" ]
}
