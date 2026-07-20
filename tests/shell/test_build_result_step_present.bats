#!/usr/bin/env bats
# Confirms all 6 write-capable agent defs carry the "Write Result File" step
# (stall-fix Slice B) and that it is positioned after the commit anchor.
# A 5-of-6 partial edit (one agent def missed) must go RED here.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  AGENTS_DIR="$REPO_ROOT/agents"
}

line_of() {
  grep -n -m1 "$2" "$1" | cut -d: -f1
}

@test "all 6 write-capable agent defs contain the Write Result File step" {
  local count=0
  local agent
  for agent in software-engineer fix-engineer frontend-engineer database-engineer qa-engineer infrastructure-engineer; do
    if grep -q "Write Result File" "$AGENTS_DIR/$agent.md"; then
      count=$((count + 1))
    fi
  done
  [ "$count" -eq 6 ]
}

@test "software-engineer.md step is after the Commit Cadence anchor" {
  local commit_line step_line
  commit_line=$(line_of "$AGENTS_DIR/software-engineer.md" "^## Commit Cadence")
  step_line=$(line_of "$AGENTS_DIR/software-engineer.md" "Write Result File")
  [ "$step_line" -gt "$commit_line" ]
}

@test "database-engineer.md step is after the Commit Cadence anchor" {
  local commit_line step_line
  commit_line=$(line_of "$AGENTS_DIR/database-engineer.md" "^## Commit Cadence")
  step_line=$(line_of "$AGENTS_DIR/database-engineer.md" "Write Result File")
  [ "$step_line" -gt "$commit_line" ]
}

@test "qa-engineer.md step is after the Commit Cadence anchor" {
  local commit_line step_line
  commit_line=$(line_of "$AGENTS_DIR/qa-engineer.md" "^## Commit Cadence")
  step_line=$(line_of "$AGENTS_DIR/qa-engineer.md" "Write Result File")
  [ "$step_line" -gt "$commit_line" ]
}

@test "infrastructure-engineer.md step is after the Commit Cadence anchor" {
  local commit_line step_line
  commit_line=$(line_of "$AGENTS_DIR/infrastructure-engineer.md" "^## Commit Cadence")
  step_line=$(line_of "$AGENTS_DIR/infrastructure-engineer.md" "Write Result File")
  [ "$step_line" -gt "$commit_line" ]
}

@test "frontend-engineer.md step is after the Commit Cadence anchor" {
  local commit_line step_line
  commit_line=$(line_of "$AGENTS_DIR/frontend-engineer.md" "^## Commit Cadence")
  step_line=$(line_of "$AGENTS_DIR/frontend-engineer.md" "Write Result File")
  [ "$step_line" -gt "$commit_line" ]
}

# fix-engineer is asymmetric: its report is a fenced markdown block, not an
# "## Output Format" header, so ordering anchors on the commit step and the
# literal verdict enum string instead.
@test "fix-engineer.md step is after Step 3 commit and before the FIX_APPLIED verdict line" {
  local commit_line step_line verdict_line
  commit_line=$(line_of "$AGENTS_DIR/fix-engineer.md" "^### Step 3: Commit and report")
  step_line=$(line_of "$AGENTS_DIR/fix-engineer.md" "Write Result File")
  verdict_line=$(line_of "$AGENTS_DIR/fix-engineer.md" "verdict: FIX_APPLIED")
  [ "$step_line" -gt "$commit_line" ]
  [ "$step_line" -lt "$verdict_line" ]
}
