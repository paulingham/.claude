#!/usr/bin/env bats
# Asserts that hooks/tests/README.md is present, maps every test-*.sh to either
# a bridge or a quarantine entry, and that the fixtures/.gitkeep comment is not stale.
setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  README="$REPO_ROOT/hooks/tests/README.md"
  GITKEEP="$REPO_ROOT/hooks/tests/fixtures/.gitkeep"
}

@test "hooks/tests/README.md exists" {
  [ -f "$README" ]
}

@test "README references bridge_ bridges" {
  grep -q "bridge_" "$README"
}

@test "README covers test-auto-learn-gate.sh (bridged or quarantined)" {
  grep -q "test-auto-learn-gate.sh" "$README"
}

@test "README covers test-bash-write-guard.sh (bridged or quarantined)" {
  grep -q "test-bash-write-guard.sh" "$README"
}

@test "README covers test-build-loop-scan.sh (bridged or quarantined)" {
  grep -q "test-build-loop-scan.sh" "$README"
}

@test "README covers test-cache-feed-bugs.sh (bridged or quarantined)" {
  grep -q "test-cache-feed-bugs.sh" "$README"
}

@test "README covers test-cost-feed-router-signals.sh (bridged or quarantined)" {
  grep -q "test-cost-feed-router-signals.sh" "$README"
}

@test "README covers test-detect-stale-pipeline-state.sh (bridged or quarantined)" {
  grep -q "test-detect-stale-pipeline-state.sh" "$README"
}

@test "README covers test-eval-capture-hook.sh (bridged or quarantined)" {
  grep -q "test-eval-capture-hook.sh" "$README"
}

@test "README covers test-eval-model-effectiveness.sh (bridged or quarantined)" {
  grep -q "test-eval-model-effectiveness.sh" "$README"
}

@test "README covers test-harness-paths.sh (bridged or quarantined)" {
  grep -q "test-harness-paths.sh" "$README"
}

@test "README covers test-hook-registration-invariant.sh (bridged or quarantined)" {
  grep -q "test-hook-registration-invariant.sh" "$README"
}

@test "README covers test-hooks-json.sh (bridged or quarantined)" {
  grep -q "test-hooks-json.sh" "$README"
}

@test "README covers test-hooks.sh (bridged or quarantined)" {
  grep -q "test-hooks.sh" "$README"
}

@test "README covers test-intake-backstop.sh (bridged or quarantined)" {
  grep -q "test-intake-backstop.sh" "$README"
}

@test "README covers test-main-branch-guard.sh (bridged or quarantined)" {
  grep -q "test-main-branch-guard.sh" "$README"
}

@test "README covers test-managed-settings.sh (bridged or quarantined)" {
  grep -q "test-managed-settings.sh" "$README"
}

@test "README covers test-nested-pipeline-isolation.sh (bridged or quarantined)" {
  grep -q "test-nested-pipeline-isolation.sh" "$README"
}

@test "README covers test-pipeline-analytics.sh (bridged or quarantined)" {
  grep -q "test-pipeline-analytics.sh" "$README"
}

@test "README covers test-pipeline-entry-guard.sh (bridged or quarantined)" {
  grep -q "test-pipeline-entry-guard.sh" "$README"
}

@test "README covers test-plan-cache-lookup.sh (bridged or quarantined)" {
  grep -q "test-plan-cache-lookup.sh" "$README"
}

@test "README covers test-pytest-suite-guard.sh (bridged or quarantined)" {
  grep -q "test-pytest-suite-guard.sh" "$README"
}

@test "README covers test-quality-gate-diff-scope.sh (bridged or quarantined)" {
  grep -q "test-quality-gate-diff-scope.sh" "$README"
}

@test "README covers test-quality-gate-freshness.sh (bridged or quarantined)" {
  grep -q "test-quality-gate-freshness.sh" "$README"
}

@test "README covers test-root-tree-clean-check.sh (bridged or quarantined)" {
  grep -q "test-root-tree-clean-check.sh" "$README"
}

@test "README covers test-runtime-state-guard.sh (bridged or quarantined)" {
  grep -q "test-runtime-state-guard.sh" "$README"
}

@test "README covers test-session-start-bootstrap.sh (bridged or quarantined)" {
  grep -q "test-session-start-bootstrap.sh" "$README"
}

@test "README covers test-syntax-check.sh (bridged or quarantined)" {
  grep -q "test-syntax-check.sh" "$README"
}

@test "fixtures/.gitkeep comment is not stale (no project-hash reference)" {
  ! grep -q "project-hash" "$GITKEEP"
}
