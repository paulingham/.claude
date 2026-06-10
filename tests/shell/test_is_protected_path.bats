#!/usr/bin/env bats
# Slice A — ACs A1-A8: is-protected-path.sh helper
#
# Builds a REAL git repo whose top-level directory name contains `.claude`
# (to mirror the harness repo root), commits agents/existing.md so that
# the parent-probe step (Step 4) finds a tracked sibling, and validates all
# eight acceptance criteria.
#
# Ubuntu trap: NO literal '@test' substring inside any heredoc or string.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HELPER="$REPO_ROOT/hooks/_lib/is-protected-path.sh"

  # Build a fresh real git repo whose toplevel name contains ".claude"
  TMPDIR_BASE="$(mktemp -d)"
  PROJECT_DIR="$TMPDIR_BASE/proj.claude"
  mkdir -p "$PROJECT_DIR"
  git -C "$PROJECT_DIR" init -q
  git -C "$PROJECT_DIR" config user.email "test@test"
  git -C "$PROJECT_DIR" config user.name "Test"

  # Commit agents/existing.md so Step 4 has a tracked sibling in agents/
  mkdir -p "$PROJECT_DIR/agents"
  echo "# existing" > "$PROJECT_DIR/agents/existing.md"
  git -C "$PROJECT_DIR" add agents/existing.md
  git -C "$PROJECT_DIR" commit -q -m "seed"

  # Also seed hooks/ with a tracked file for hooks/ parent-probe
  mkdir -p "$PROJECT_DIR/hooks"
  echo "#!/bin/bash" > "$PROJECT_DIR/hooks/existing.sh"
  git -C "$PROJECT_DIR" add hooks/existing.sh
  git -C "$PROJECT_DIR" commit -q -m "hooks seed"
}

teardown() {
  rm -rf "$TMPDIR_BASE"
}

# Source helper and call is_protected_path $1, return its exit code
_run_helper() {
  bash -c "source '$HELPER'; is_protected_path '$1'"
  echo "$?"
}

# A1: tracked file → exit 0 (BLOCK)
@test "A1_tracked_agents_existing_md_blocks" {
  result=$(bash -c "source '$HELPER'; is_protected_path '$PROJECT_DIR/agents/existing.md'; echo \$?")
  [ "$result" = "0" ]
}

# A2: net-new file in agents/ (tracked dir) → exit 0 (BLOCK)
@test "A2_net_new_agents_new_x_md_blocks" {
  result=$(bash -c "source '$HELPER'; is_protected_path '$PROJECT_DIR/agents/new-x.md'; echo \$?")
  [ "$result" = "0" ]
}

# A3: net-new file in hooks/ (tracked dir) → exit 0 (BLOCK)
@test "A3_net_new_hooks_new_y_sh_blocks" {
  result=$(bash -c "source '$HELPER'; is_protected_path '$PROJECT_DIR/hooks/new-y.sh'; echo \$?")
  [ "$result" = "0" ]
}

# A4: net-new file in untracked scratch dir (no tracked siblings) → exit 1 (ALLOW)
@test "A4_net_new_in_untracked_scratch_dir_allows" {
  mkdir -p "$PROJECT_DIR/scratch-untracked"
  result=$(bash -c "source '$HELPER'; is_protected_path '$PROJECT_DIR/scratch-untracked/file.md'; echo \$?")
  [ "$result" = "1" ]
}

# A5: pipeline-state path → exit 1 (ALLOW via substring allowlist)
@test "A5_pipeline_state_allows" {
  result=$(bash -c "source '$HELPER'; is_protected_path '/abs/pipeline-state/new-task/plan.md'; echo \$?")
  [ "$result" = "1" ]
}

# A6: learning/*.jsonl → exit 1 (ALLOW via regex allowlist)
@test "A6_learning_jsonl_allows" {
  result=$(bash -c "source '$HELPER'; is_protected_path '/abs/learning/obs/x.jsonl'; echo \$?")
  [ "$result" = "1" ]
}

# A7: target whose parent dir doesn't exist → exit 0 (BLOCK via fail-closed)
@test "A7_nonexistent_parent_blocks" {
  result=$(bash -c "source '$HELPER'; is_protected_path '/does-not-exist-dir-$$$/file.md'; echo \$?")
  [ "$result" = "0" ]
}

# A8: set -uo pipefail sourcing produces no unbound-var error
@test "A8_no_unbound_var_error_under_strict_mode" {
  out=$(bash -c "set -uo pipefail; source '$HELPER'; is_protected_path '/tmp/x'; echo OK" 2>&1)
  echo "$out" | grep -q "OK"
}
