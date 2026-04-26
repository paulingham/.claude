#!/usr/bin/env bats
# Slice 3 — worktree-cwd-check.sh post-hoc diagnostic + subagent_id trajectory.
# Hermetic: $HOME→mktemp; hooks/ symlinked; pipeline-state seeded with an
# in_progress task so _wcc_resolve_task_id picks it up; metrics violations log
# pre-seeded to drive prevented→post-confirmed pairing and cursor idempotency.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  TMP_HOME="$(mktemp -d)"
  mkdir -p "$TMP_HOME/.claude"
  rm -rf "$TMP_HOME/.claude/hooks"
  ln -sfn "$REPO_ROOT/hooks" "$TMP_HOME/.claude/hooks"
  export HOME="$TMP_HOME"
  export CLAUDE_HOOK_PROFILE="minimal"
  export CLAUDE_SESSION_ID="bats-wcc-$$"
  export CLAUDE_PIPELINE_TASK_ID="wcc-test-task"
  mkdir -p "$HOME/.claude/state" "$HOME/.claude/pipeline-state"
  mkdir -p "$HOME/.claude/metrics/$CLAUDE_SESSION_ID"
  LOG="$HOME/.claude/metrics/$CLAUDE_SESSION_ID/main-branch-violations.jsonl"
  CURSOR="$HOME/.claude/state/worktree-cwd-check-cursor-${CLAUDE_PIPELINE_TASK_ID}"
}

teardown() {
  rm -rf "$TMP_HOME"
  unset HOME CLAUDE_HOOK_PROFILE CLAUDE_SESSION_ID CLAUDE_PIPELINE_TASK_ID
}

# Helper: append a "prevented" entry to the violations log.
_seed_prevented() {
  printf '{"timestamp":"%s","session_id":"%s","task_id":"%s","command":"%s","source":"prevented","action":"prevented"}\n' \
    "2026-04-26T00:00:00Z" "$CLAUDE_SESSION_ID" "$CLAUDE_PIPELINE_TASK_ID" "$1" >> "$LOG"
}

# Helper: count entries with a given source value.
_count_source() {
  local src="$1"
  [ -f "$LOG" ] || { echo 0; return; }
  grep -c "\"source\":\"$src\"" "$LOG" || true
}

# Helper: pipe empty stdin into worktree-cwd-check (matches SubagentStop input).
_run_check() {
  printf '{}' | bash "$REPO_ROOT/hooks/worktree-cwd-check.sh"
}

# ---------------------------------------------------------------------------
# AC3.1-AC3.7
# ---------------------------------------------------------------------------

@test "AC3.1 hook always exits 0" {
  run _run_check
  [ "$status" -eq 0 ]
}

@test "AC3.2 prevented entry → paired post-confirmed entry appended" {
  _seed_prevented "git checkout foo"
  _seed_prevented "gh pr create"
  run _run_check
  [ "$status" -eq 0 ]
  [ "$(_count_source post-confirmed)" -ge 2 ]
}

@test "AC3.3 cursor at end → no new post-confirmed entries appended" {
  _seed_prevented "git checkout foo"
  _run_check               # first run: pairs the entry
  before=$(_count_source post-confirmed)
  _run_check               # second run: cursor at end, should pair nothing
  after=$(_count_source post-confirmed)
  [ "$before" = "$after" ]
}

@test "AC3.4 REPO_ROOT HEAD ≠ main → drift-detected entry appended" {
  # Build a hermetic repo at $HOME/.claude (the diagnostic targets $HOME/.claude).
  ( cd "$HOME/.claude" && git init -q -b feat/x )
  ( cd "$HOME/.claude" && git config user.email t@t && git config user.name t )
  ( cd "$HOME/.claude" && git commit -q --allow-empty -m init )
  run _run_check
  [ "$status" -eq 0 ]
  [ "$(_count_source drift-detected)" -ge 1 ]
  last_drift=$(grep '"source":"drift-detected"' "$LOG" | tail -1)
  [ "$(echo "$last_drift" | jq -r .current_head)" = "feat/x" ]
}

@test "AC3.5 no active pipeline → exit 0, no writes" {
  unset CLAUDE_PIPELINE_TASK_ID
  rm -rf "$HOME/.claude/pipeline-state"
  mkdir -p "$HOME/.claude/pipeline-state"  # empty (no in_progress files)
  rm -f "$LOG"
  run _run_check
  [ "$status" -eq 0 ]
  [ ! -f "$LOG" ] || [ "$(wc -l < "$LOG" | tr -d ' ')" = "0" ]
}

@test "AC3.6 hook file ≤50 lines, function bodies ≤5 lines" {
  hook="$REPO_ROOT/hooks/worktree-cwd-check.sh"
  lc=$(wc -l < "$hook" | tr -d ' ')
  [ "$lc" -le 50 ] || { echo "worktree-cwd-check.sh has $lc lines (>50)"; false; }
  # Function-body shape: every defined function body ≤5 lines (open-brace-to-close-brace).
  # Heuristic: detect `^_wcc_.*\(\) {` openers, count lines until matching `^}`.
  awk '/^_wcc_[a-z_]*\(\) \{/ {start=NR; name=$0; depth=1; next}
       depth==1 && /^}/ { lines=NR-start-1; if (lines>5) {print name " body=" lines; bad=1}; depth=0 }
       END { exit bad+0 }' "$hook"
}

# Helper: extract the LAST record from a multi-record JSONL file when records
# may be pretty-printed (jq -n default emits multi-line JSON). `jq -s` slurps
# the entire file into an array; `.[-1]` picks the last record.
_last_record() {
  jq -s '.[-1]' "$1"
}

@test "AC3.7 subagent-stop-trajectory.sh records contain a subagent_id field" {
  TRAJ_FILE="$HOME/.claude/pipeline-state/${CLAUDE_PIPELINE_TASK_ID}-trajectory.jsonl"
  printf '{"subagent_type":"software-engineer","subagent_id":"explicit-id-42"}' \
    | bash "$REPO_ROOT/hooks/subagent-stop-trajectory.sh"
  [ -f "$TRAJ_FILE" ]
  [ "$(_last_record "$TRAJ_FILE" | jq -r .subagent_id)" = "explicit-id-42" ]
}

@test "AC3.7b subagent_id falls back to a non-empty derived value when not provided" {
  TRAJ_FILE="$HOME/.claude/pipeline-state/${CLAUDE_PIPELINE_TASK_ID}-trajectory.jsonl"
  printf '{"subagent_type":"software-engineer"}' \
    | bash "$REPO_ROOT/hooks/subagent-stop-trajectory.sh"
  derived=$(_last_record "$TRAJ_FILE" | jq -r .subagent_id)
  # Pattern: <session>-<rand>-<pid> per Engineer A scratchpad. Regex-match, not literal.
  [[ "$derived" =~ ^.+-[0-9]+-[0-9]+$ ]]
}

@test "Multi-agent: two SubagentStop calls record distinct subagent_ids" {
  TRAJ_FILE="$HOME/.claude/pipeline-state/${CLAUDE_PIPELINE_TASK_ID}-trajectory.jsonl"
  printf '{"subagent_type":"software-engineer","subagent_id":"agent-A"}' \
    | bash "$REPO_ROOT/hooks/subagent-stop-trajectory.sh"
  printf '{"subagent_type":"code-reviewer","subagent_id":"agent-B"}' \
    | bash "$REPO_ROOT/hooks/subagent-stop-trajectory.sh"
  ids=$(jq -s '[.[].subagent_id] | unique | length' "$TRAJ_FILE")
  [ "$ids" = "2" ]
}

# HIGH-5 (security) — CLAUDE_SESSION_ID with traversal must NOT escape metrics dir.
@test "AC3.8 traversal CLAUDE_SESSION_ID is sanitized in cwd-check" {
  ( cd "$HOME/.claude" && git init -q -b feat/x \
    && git config user.email t@t && git config user.name t \
    && git commit -q --allow-empty -m drift )
  # Pre-create the parent of the traversed path so a successful escape would write a file.
  mkdir -p "$HOME/.claude/metrics/../../etc"
  CLAUDE_SESSION_ID="../../etc" run _run_check
  [ "$status" -eq 0 ]
  # No log file outside metrics tree.
  [ ! -f "$HOME/etc/main-branch-violations.jsonl" ]
  [ ! -f "$HOME/.claude/etc/main-branch-violations.jsonl" ]
  # The drift-detected entry MUST land under metrics/ at a sanitized session dir
  # (sanitization strips `/` from the session id, leaving `....etc`).
  ls "$HOME/.claude/metrics/" >/dev/null 2>&1
  found=$(find "$HOME/.claude/metrics" -name "main-branch-violations.jsonl" 2>/dev/null | wc -l | tr -d ' ')
  [ "$found" -ge 1 ]
}

# MEDIUM-1 — repo_root MUST be parameterizable via CLAUDE_REPO_ROOT.
@test "AC3.9 CLAUDE_REPO_ROOT overrides hardcoded HOME/.claude in drift check" {
  ALT_ROOT=$(mktemp -d)/altrepo
  mkdir -p "$ALT_ROOT"
  ( cd "$ALT_ROOT" && git init -q -b feat/alt \
    && git config user.email t@t && git config user.name t \
    && git commit -q --allow-empty -m alt )
  CLAUDE_REPO_ROOT="$ALT_ROOT" run _run_check
  [ "$status" -eq 0 ]
  # Drift on alt repo should be detected.
  [ "$(_count_source drift-detected)" -ge 1 ]
  last_drift=$(grep '"source":"drift-detected"' "$LOG" | tail -1)
  [ "$(echo "$last_drift" | jq -r .current_head)" = "feat/alt" ]
  rm -rf "$(dirname "$ALT_ROOT")"
}

# MEDIUM-2 — corrupt cursor file MUST be reset to 0, not propagate garbage.
@test "AC3.10 corrupt cursor file resets to 0 (no garbage offsets)" {
  _seed_prevented "git checkout foo"
  # Pre-poison the cursor with non-numeric garbage.
  printf '%s' "not-a-number" > "$CURSOR"
  run _run_check
  [ "$status" -eq 0 ]
  # post-confirmed entries SHOULD have been emitted (cursor reset to 0 means we re-paired).
  [ "$(_count_source post-confirmed)" -ge 1 ]
  # And the cursor MUST now hold a non-negative integer.
  cursor_val=$(cat "$CURSOR")
  [[ "$cursor_val" =~ ^[0-9]+$ ]]
}
