#!/usr/bin/env bats
# Over-spawn guard bats tests — AC1-AC5 (CI-gating, tests/shell/*.bats).
#
# Seeds pipeline-state and counter files to drive pre-agent-over-spawn-guard.sh.
# All tests verify exit 0 (advisory invariant) + check JSONL presence/absence.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK="$REPO_ROOT/hooks/pre-agent-over-spawn-guard.sh"
  TMP="$(mktemp -d -t osg.XXXXXX)"
  export HOME="$TMP"
  export CLAUDE_SESSION_ID="osg-test-$$"
  export HARNESS_DATA="$TMP/.claude"
  mkdir -p "$TMP/.claude/pipeline-state" "$TMP/.claude/metrics"
  unset CLAUDE_DISABLE_OVER_SPAWN_GUARD CLAUDE_HOOK_PROFILE
  METRICS_DIR="$TMP/.claude/metrics/$CLAUDE_SESSION_ID"
  STATE_DIR="$TMP/.claude/pipeline-state"
  WARNINGS_JSONL="$METRICS_DIR/over-spawn-warnings.jsonl"
}

teardown() {
  [ -d "$TMP" ] && rm -rf "$TMP"
}

# Helper: seed a minimal in-progress plan.md (v1-style, 1 slice)
_seed_task() {
  local task_id="$1"
  mkdir -p "$STATE_DIR/$task_id"
  cat > "$STATE_DIR/$task_id/plan.md" << PLANEOF
---
task_id: ${task_id}
phase: plan
verdict: in_progress
---

# Plan
PLANEOF
}

# Helper: seed a v2 DAG plan with N slices
_seed_v2_task() {
  local task_id="$1"
  local n_slices="$2"
  mkdir -p "$STATE_DIR/$task_id"
  local plan_file="$STATE_DIR/$task_id/plan.md"
  {
    echo "---"
    echo "task_id: ${task_id}"
    echo "schema_version: 2"
    echo "phase: plan"
    echo "verdict: in_progress"
    echo "---"
    echo ""
    echo "# Plan"
    echo ""
    echo "## Slices"
    echo ""
    echo '```yaml'
    echo "slices:"
    local i=1
    while [ "$i" -le "$n_slices" ]; do
      if [ "$i" -eq 1 ]; then
        echo "  - id: slice-${i}"
        echo "    depends-on: []"
        echo "    description: Slice ${i}"
      else
        prev=$((i - 1))
        echo "  - id: slice-${i}"
        echo "    depends-on: [slice-${prev}]"
        echo "    description: Slice ${i}"
      fi
      i=$((i + 1))
    done
    echo '```'
  } > "$plan_file"
}

# Helper: pre-seed a counter file to simulate prior spawns
_seed_counter() {
  local task_id="$1"
  local phase="$2"
  local count="$3"
  local counter_dir="$METRICS_DIR/over-spawn"
  mkdir -p "$counter_dir"
  echo -n "$count" > "$counter_dir/${task_id}--${phase}.count"
}

# Helper: write payload JSON to a temp file and return the path
_payload_file() {
  local role="$1"
  local tmpf
  tmpf="$(mktemp "$TMP/payload.XXXXXX")"
  cat > "$tmpf" << PAYEOF
{"tool_name":"Agent","tool_input":{"prompt":"Read ~/.claude/agents/${role}.md for your full role","subagent_type":"${role}"},"session_id":"${CLAUDE_SESSION_ID}"}
PAYEOF
  echo "$tmpf"
}

# -----------------------------------------------------------------------
# AC1: final-gate 4-on-1-slice warns (literal spec case)
# -----------------------------------------------------------------------

@test "AC1 final-gate 4th spawn on 1-slice task writes warn record" {
  _seed_task "my-task"
  _seed_counter "my-task" "final-gate" 3   # 3 prior spawns; 4th will exceed ceiling=1
  local pf
  pf="$(_payload_file patch-critic)"

  run bash -c "bash '$HOOK' < '$pf'"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
  [ -f "$WARNINGS_JSONL" ]
  grep -q '"phase"' "$WARNINGS_JSONL"
  grep -q 'final-gate' "$WARNINGS_JSONL"
  grep -q '"spawn_count": *4' "$WARNINGS_JSONL"
  grep -q '"ceiling": *1' "$WARNINGS_JSONL"
  grep -q '"slice_count": *1' "$WARNINGS_JSONL"
  grep -q '"task_id"' "$WARNINGS_JSONL"
  grep -q 'my-task' "$WARNINGS_JSONL"
}

@test "AC1 final-gate 5th agent on 1-slice warns (realistic 5-agent gate)" {
  _seed_task "my-task"
  _seed_counter "my-task" "final-gate" 4   # 4 prior spawns; 5th will exceed ceiling=1
  local pf
  pf="$(_payload_file qa-engineer)"

  run bash -c "bash '$HOOK' < '$pf'"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
  [ -f "$WARNINGS_JSONL" ]
  grep -q '"spawn_count": *5' "$WARNINGS_JSONL"
}

# -----------------------------------------------------------------------
# AC2: build N-on-N does NOT write a warn record
# -----------------------------------------------------------------------

@test "AC2 build 4-on-4-slice task writes NO warn record" {
  _seed_v2_task "dag-task" 4
  local pf
  pf="$(_payload_file software-engineer)"
  # Simulate 4 build spawns — ceiling==4, so none should trigger a warning
  local i=1
  while [ "$i" -le 4 ]; do
    run bash -c "bash '$HOOK' < '$pf'"
    [ "$status" -eq 0 ]
    [ -z "$output" ]
    i=$((i + 1))
  done
  [ ! -f "$WARNINGS_JSONL" ]
}

# -----------------------------------------------------------------------
# AC3: exit 0 + empty stdout on warn; exit 0 on malformed stdin; no pipeline
# -----------------------------------------------------------------------

@test "AC3 hook exits 0 with empty stdout even when warn fires" {
  _seed_task "warn-task"
  _seed_counter "warn-task" "final-gate" 3
  local pf
  pf="$(_payload_file patch-critic)"

  run bash -c "bash '$HOOK' < '$pf'"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "AC3 hook exits 0 on malformed stdin (no record written)" {
  run bash -c "echo 'not-json' | bash '$HOOK'"
  [ "$status" -eq 0 ]
  [ ! -f "$WARNINGS_JSONL" ]
}

@test "AC3 no active pipeline produces exit 0 and no warn record" {
  # No plan.md seeded → no active pipeline
  local pf
  pf="$(_payload_file patch-critic)"

  run bash -c "bash '$HOOK' < '$pf'"
  [ "$status" -eq 0 ]
  [ ! -f "$WARNINGS_JSONL" ]
}

# -----------------------------------------------------------------------
# AC5: bypass variables skip the guard entirely
# -----------------------------------------------------------------------

@test "AC5 CLAUDE_DISABLE_OVER_SPAWN_GUARD=1 exits 0 and writes no record" {
  _seed_task "bypass-task"
  _seed_counter "bypass-task" "final-gate" 9   # Would normally warn
  local pf
  pf="$(_payload_file patch-critic)"

  run bash -c "CLAUDE_DISABLE_OVER_SPAWN_GUARD=1 bash '$HOOK' < '$pf'"
  [ "$status" -eq 0 ]
  [ ! -f "$WARNINGS_JSONL" ]
}

@test "AC5 CLAUDE_HOOK_PROFILE=minimal exits 0 and writes no record" {
  _seed_task "minimal-task"
  _seed_counter "minimal-task" "final-gate" 9   # Would normally warn
  local pf
  pf="$(_payload_file patch-critic)"

  run bash -c "CLAUDE_HOOK_PROFILE=minimal bash '$HOOK' < '$pf'"
  [ "$status" -eq 0 ]
  [ ! -f "$WARNINGS_JSONL" ]
}

# -----------------------------------------------------------------------
# AC1: 4-slice DAG resolves ceiling correctly (slice_count from plan.md)
# -----------------------------------------------------------------------

@test "AC1 4-slice DAG plan resolves ceiling=2 for final-gate; 3rd spawn warns" {
  _seed_v2_task "dag-task" 4
  # final-gate ceiling for 4-slice = ceil(4/2) = 2
  # seed 2 prior final-gate spawns; 3rd exceeds ceiling
  _seed_counter "dag-task" "final-gate" 2
  local pf
  pf="$(_payload_file patch-critic)"

  run bash -c "bash '$HOOK' < '$pf'"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
  [ -f "$WARNINGS_JSONL" ]
  grep -q '"ceiling": *2' "$WARNINGS_JSONL"
  grep -q '"slice_count": *4' "$WARNINGS_JSONL"
  grep -q '"spawn_count": *3' "$WARNINGS_JSONL"
}
