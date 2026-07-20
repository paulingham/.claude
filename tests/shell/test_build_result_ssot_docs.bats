#!/usr/bin/env bats
# Doc-structure guards for stall-fix Slice C (SSOT contract in the skill and
# orchestrator docs). These assertions git-grep the COMMITTED tree, so this
# suite must be run AFTER committing the Slice C doc edits.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  SKILL="$REPO_ROOT/skills/build-implementation/SKILL.md"
  ORCH="$REPO_ROOT/orchestrator/pipeline-orchestration.md"
}

line_of() {
  git -C "$REPO_ROOT" grep -n -m1 "$2" -- "$1" | head -1 | cut -d: -f2
}

@test "AC6 skill names build-result.json as the SSOT" {
  git -C "$REPO_ROOT" grep -q "Completion Signal (SSOT)" -- skills/build-implementation/SKILL.md
  git -C "$REPO_ROOT" grep -q "build-result.json" -- skills/build-implementation/SKILL.md
  git -C "$REPO_ROOT" grep -q "machine-readable source of truth" -- skills/build-implementation/SKILL.md
}

@test "AC6 Phase Output prose is demoted, not deleted" {
  git -C "$REPO_ROOT" grep -q "## Phase Output" -- skills/build-implementation/SKILL.md
  git -C "$REPO_ROOT" grep -q "human-facing summary; it is not the machine signal" -- skills/build-implementation/SKILL.md
}

@test "AC6 Completion Signal subsection appears before Phase Output in the skill" {
  local ssot_line phase_output_line
  ssot_line=$(line_of "skills/build-implementation/SKILL.md" "### Completion Signal (SSOT)")
  phase_output_line=$(line_of "skills/build-implementation/SKILL.md" "^## Phase Output")
  [ -n "$ssot_line" ]
  [ -n "$phase_output_line" ]
  [ "$ssot_line" -lt "$phase_output_line" ]
}

@test "AC7 orchestrator doc names the reader and reads it before advancing" {
  git -C "$REPO_ROOT" grep -q "Detecting Build Completion" -- orchestrator/pipeline-orchestration.md
  git -C "$REPO_ROOT" grep -q "build_result_reader.py" -- orchestrator/pipeline-orchestration.md
  git -C "$REPO_ROOT" grep -q "Read the file FIRST" -- orchestrator/pipeline-orchestration.md
}

@test "AC7 orchestrator doc contains the branch-recovery fallback for MISSING/CORRUPT" {
  git -C "$REPO_ROOT" grep -q "branch-recovery" -- orchestrator/pipeline-orchestration.md
  git -C "$REPO_ROOT" grep -q "git -C \"\$WORKTREE\" log <base>..HEAD" -- orchestrator/pipeline-orchestration.md
}

@test "AC7 orchestrator doc cites the fail-closed / Iron Law 8 contract" {
  git -C "$REPO_ROOT" grep -q "Iron Law 8" -- orchestrator/pipeline-orchestration.md
  git -C "$REPO_ROOT" grep -q "NEVER be treated as\|NEVER treated as" -- orchestrator/pipeline-orchestration.md
}

# RED-on-reorder/removal canary: the orchestrator doc must place "Read the
# file FIRST" ahead of any prose-parsing language, and the branch-recovery
# fallback line must exist. If a future edit reorders the read-path to parse
# prose first, or drops the fallback, this test goes RED.
@test "CANARY Detecting Build Completion precedes Team State and keeps the fallback" {
  local detect_line team_state_line
  detect_line=$(line_of "orchestrator/pipeline-orchestration.md" "### Detecting Build Completion")
  team_state_line=$(line_of "orchestrator/pipeline-orchestration.md" "^### Team State")
  [ -n "$detect_line" ]
  [ -n "$team_state_line" ]
  [ "$detect_line" -lt "$team_state_line" ]
  git -C "$REPO_ROOT" grep -q "never treated as \`BUILD_COMPLETE\`\|NEVER treated as" -- orchestrator/pipeline-orchestration.md
}
