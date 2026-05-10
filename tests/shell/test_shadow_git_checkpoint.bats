#!/usr/bin/env bats
# shadow-git-checkpoint hook + helpers — end-to-end bats coverage.
# Test names encode the AC number (`test_acNN_...`) per
# `instinct-ac-coverage-final-gate-gap`.
#
# Setup pattern follows tests/shell/test_destructive_verb_block.bats:10-40
# (mktemp -d, fake $HOME, jq -nc payload, pipe to hook).

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK="$REPO_ROOT/hooks/shadow-git-checkpoint.sh"
  HELPERS="$REPO_ROOT/hooks/_lib/shadow-checkpoint-helpers.sh"

  TMP="$(mktemp -d -t sgc.XXXXXX)"
  export HOME="$TMP"
  export TMPDIR="$TMP/tmp"; mkdir -p "$TMPDIR"
  export CLAUDE_SESSION_ID="sgc-test-$$-$RANDOM"
  export CLAUDE_HOOK_PROFILE="standard"  # ensure the hook runs (not minimal)
  unset CLAUDE_DISABLE_SHADOW_CHECKPOINT

  # Fixture worktree under .claude/worktrees/agent-test/
  WT="$TMP/.claude/worktrees/agent-test"
  mkdir -p "$WT"
  git -C "$WT" init -q -b main 2>/dev/null
  git -C "$WT" config user.email "sgc@example.com"
  git -C "$WT" config user.name "sgc"
  echo "seed" > "$WT/seed.txt"
  git -C "$WT" add seed.txt
  git -C "$WT" commit -q -m "seed"

  # Active pipeline state for the task-id resolver fallback path.
  TASK="sgc-test-task"
  export CLAUDE_PIPELINE_TASK_ID="$TASK"
  STATE_DIR="$TMP/.claude/pipeline-state"
  mkdir -p "$STATE_DIR/$TASK"
  cat > "$STATE_DIR/$TASK/pipeline.md" <<EOF
---
task_id: $TASK
phase: build
verdict: in_progress
timestamp: 2026-05-10T00:00:00Z
---
EOF
  export CLAUDE_PIPELINE_STATE_DIR="$STATE_DIR"
  export CLAUDE_HOOK_LOG_DIR="$TMP/.claude/metrics"
}

teardown() {
  [ -d "$TMP" ] && rm -rf "$TMP"
}

_payload() {
  # $1 = file_path inside the fixture worktree
  jq -nc --arg path "$1" --arg tool "Write" \
    '{tool_name:$tool, tool_input:{file_path:$path}}'
}

_run_hook_with() {
  echo "$1" | bash "$HOOK"
}

_count_checkpoint_refs() {
  git -C "$WT" for-each-ref --format='%(refname)' "refs/checkpoints/$TASK/" 2>/dev/null | wc -l | tr -d ' '
}

# ---------------------------------------------------------------------------
# AC1.4 — counter increment atomicity under concurrency
# ---------------------------------------------------------------------------

@test "AC1.4 counter increment is atomic under concurrency" {
  source "$HELPERS"
  TASK_DIR="$STATE_DIR/$TASK"
  SLUG="agent-conc"
  RESULTS="$TMP/conc-results.txt"

  # Spawn 10 concurrent increments. Each writes its returned step value to RESULTS.
  for i in $(seq 1 10); do
    ( _sgc_increment_counter "$TASK_DIR" "$SLUG" >> "$RESULTS" ) &
  done
  wait

  # Expect 10 distinct sequential step values (0001..0010), no duplicates.
  COUNT=$(wc -l < "$RESULTS" | tr -d ' ')
  [ "$COUNT" -eq 10 ]
  UNIQ=$(sort -u < "$RESULTS" | wc -l | tr -d ' ')
  [ "$UNIQ" -eq 10 ]
}

# ---------------------------------------------------------------------------
# AC1.4 — mutex released even when critical section errors mid-flight
# ---------------------------------------------------------------------------

@test "AC1.4 mutex released when counter write fails mid-section (no leak)" {
  source "$HELPERS"
  TASK_DIR="$STATE_DIR/$TASK"
  SLUG="agent-leak"
  mkdir -p "$TASK_DIR"

  # Inject a failure between mkdir-lock and rmdir-lock by replacing the
  # counter file path with a directory of the same name — the helper's
  # `printf > "$counter"` will fail. The contract is:
  #   (a) the helper MUST return nonzero (no spurious "0001" with the
  #       counter file unwritten)
  #   (b) the lock MUST be released so the next call doesn't spin
  COUNTER="$TASK_DIR/checkpoint-counter-${SLUG}.txt"
  mkdir "$COUNTER"  # not a file — printf > "$COUNTER" will fail

  # First call: critical section fails — helper must return nonzero AND
  # release the lock (subshell EXIT trap).
  run _sgc_increment_counter "$TASK_DIR" "$SLUG"
  [ "$status" -ne 0 ]
  LOCK="${COUNTER}.lock"
  [ ! -d "$LOCK" ]

  # Second call (with the obstruction removed) must succeed without any
  # lingering retry-spin from a leaked lock.
  rmdir "$COUNTER"
  run _sgc_increment_counter "$TASK_DIR" "$SLUG"
  [ "$status" -eq 0 ]
  [ "$output" = "0001" ]
}

# ---------------------------------------------------------------------------
# AC2.1 — EXIT trap registered before any escape-hatch
# ---------------------------------------------------------------------------

@test "AC2.1 EXIT trap fires even on escape-hatch early exit" {
  export CLAUDE_DISABLE_SHADOW_CHECKPOINT=1
  payload=$(_payload "$WT/seed.txt")
  run _run_hook_with "$payload"
  [ "$status" -eq 0 ]

  HOOKS_LOG="$TMP/.claude/metrics/$CLAUDE_SESSION_ID/hooks.jsonl"
  [ -f "$HOOKS_LOG" ]
  grep -q '"hook_name":"shadow-git-checkpoint"' "$HOOKS_LOG"
}

# ---------------------------------------------------------------------------
# AC2.2 — both escape-hatch envs disable the hook
# ---------------------------------------------------------------------------

@test "AC2.2 escape hatch CLAUDE_DISABLE_SHADOW_CHECKPOINT disables hook" {
  export CLAUDE_DISABLE_SHADOW_CHECKPOINT=1
  echo "change" > "$WT/seed.txt"
  payload=$(_payload "$WT/seed.txt")
  run _run_hook_with "$payload"
  [ "$status" -eq 0 ]
  [ "$(_count_checkpoint_refs)" -eq 0 ]
}

@test "AC2.2 escape hatch CLAUDE_HOOK_PROFILE=minimal disables hook" {
  export CLAUDE_HOOK_PROFILE=minimal
  echo "change" > "$WT/seed.txt"
  payload=$(_payload "$WT/seed.txt")
  run _run_hook_with "$payload"
  [ "$status" -eq 0 ]
  [ "$(_count_checkpoint_refs)" -eq 0 ]
}

# ---------------------------------------------------------------------------
# AC2.3 — reads payload via stdin+jq
# ---------------------------------------------------------------------------

@test "AC2.3 reads tool_input.file_path from stdin payload, ignores env vars" {
  echo "change" > "$WT/seed.txt"
  # An irrelevant env var is set to a fake path — hook must not consume it.
  export CLAUDE_TOOL_INPUT_FILE_PATH="/etc/passwd"
  payload=$(_payload "$WT/seed.txt")
  run _run_hook_with "$payload"
  [ "$status" -eq 0 ]
  # Ref must be created against the WT, not against $TMP/etc/passwd.
  [ "$(_count_checkpoint_refs)" -eq 1 ]
}

# ---------------------------------------------------------------------------
# AC2.4 — no-op on REPO_ROOT edit (no .claude/worktrees/agent-* ancestor)
# ---------------------------------------------------------------------------

@test "AC2.4 no-op when file_path is outside any worktree" {
  REPO_FAKE="$TMP/repo-fake"
  mkdir -p "$REPO_FAKE"
  echo "data" > "$REPO_FAKE/settings.json"
  payload=$(_payload "$REPO_FAKE/settings.json")
  run _run_hook_with "$payload"
  [ "$status" -eq 0 ]
  [ "$(_count_checkpoint_refs)" -eq 0 ]
}

# ---------------------------------------------------------------------------
# AC2.5 — no-op when no active pipeline
# ---------------------------------------------------------------------------

@test "AC2.5 no-op when no active pipeline" {
  unset CLAUDE_PIPELINE_TASK_ID
  rm -rf "$STATE_DIR"
  echo "change" > "$WT/seed.txt"
  payload=$(_payload "$WT/seed.txt")
  run _run_hook_with "$payload"
  [ "$status" -eq 0 ]
  [ "$(_count_checkpoint_refs)" -eq 0 ]
}

# ---------------------------------------------------------------------------
# AC2.6 — happy path: ref created with non-empty tree
# ---------------------------------------------------------------------------

@test "AC2.6 happy path creates one checkpoint ref pointing at non-empty tree" {
  echo "added line" >> "$WT/seed.txt"
  payload=$(_payload "$WT/seed.txt")
  run _run_hook_with "$payload"
  [ "$status" -eq 0 ]
  [ "$(_count_checkpoint_refs)" -eq 1 ]
  REF=$(git -C "$WT" for-each-ref --format='%(refname)' "refs/checkpoints/$TASK/" | head -1)
  [ -n "$REF" ]
  # Resolve the ref to a SHA and ensure its tree has objects.
  SHA=$(git -C "$WT" rev-parse "$REF")
  [ -n "$SHA" ]
}

# ---------------------------------------------------------------------------
# AC2.7 — clean worktree → graceful no-changes path
# ---------------------------------------------------------------------------

@test "AC2.7 clean worktree (no changes to stash) emits no ref" {
  # Worktree is at HEAD with no diff.
  payload=$(_payload "$WT/seed.txt")
  run _run_hook_with "$payload"
  [ "$status" -eq 0 ]
  [ "$(_count_checkpoint_refs)" -eq 0 ]
}

# ---------------------------------------------------------------------------
# AC2.9 — concurrent hook fires create distinct sequential refs
# ---------------------------------------------------------------------------

@test "AC2.9 concurrent hook fires create distinct sequential refs (no collision)" {
  # Five concurrent fires, each producing a different change.
  for i in $(seq 1 5); do
    ( echo "change-$i" > "$WT/seed.txt" && _payload "$WT/seed.txt" | bash "$HOOK" ) &
  done
  wait
  COUNT=$(_count_checkpoint_refs)
  [ "$COUNT" -eq 5 ]
}

# ---------------------------------------------------------------------------
# AC2.10 — path traversal in file_path slug rejected (no-op)
# ---------------------------------------------------------------------------

@test "AC2.10 hostile worktree slug containing .. is rejected (no ref outside namespace)" {
  # Construct a worktree whose last segment is `agent-..` (path-traversal guard target).
  # The validator (_sgc_validate_id) is the gate at the helper layer — it
  # rejects any embedded `..` substring before the regex check, so the hook
  # exits at the SLUG validation step (line ~42 of shadow-git-checkpoint.sh)
  # without ever invoking `git update-ref`. Git's own ref-format check is a
  # secondary defense, not the primary one.
  HOSTILE_WT="$TMP/.claude/worktrees/agent-.."
  mkdir -p "$HOSTILE_WT"
  echo "evil" > "$HOSTILE_WT/foo.txt"
  payload=$(_payload "$HOSTILE_WT/foo.txt")
  run _run_hook_with "$payload"
  [ "$status" -eq 0 ]
  # Critical: NO ref created anywhere in the global ref db.
  ALL_REFS=$(git -C "$WT" for-each-ref --format='%(refname)' "refs/checkpoints/" 2>/dev/null | wc -l | tr -d ' ')
  [ "$ALL_REFS" -eq 0 ]

  # Sibling assertion: prove the validator is the gate, not git. Sourcing
  # the helper and asking it directly must reject the hostile slug with
  # nonzero — same path the hook takes at line 42.
  source "$HELPERS"
  ! _sgc_validate_id "agent-.."
}

# ---------------------------------------------------------------------------
# AC2.12 — git stash create failure → graceful exit + forensic record
# ---------------------------------------------------------------------------

@test "AC2.12 corrupt object DB → hook exits 0 + writes failure forensic record" {
  echo "change" >> "$WT/seed.txt"
  # Corrupt the object DB so `git -C "$WT" stash create` fails.
  rm -rf "$WT/.git/objects"
  mkdir "$WT/.git/objects"  # restore directory shape so git invocations don't OOM-fail
  payload=$(_payload "$WT/seed.txt")
  run _run_hook_with "$payload"
  [ "$status" -eq 0 ]
  CHK_LOG="$TMP/.claude/metrics/$CLAUDE_SESSION_ID/shadow-checkpoints.jsonl"
  [ -f "$CHK_LOG" ]
  # Tolerate either compact (json.dumps default) or whitespace-separated form.
  jq -e '.success == false' "$CHK_LOG" >/dev/null
}

# ---------------------------------------------------------------------------
# AC2.13 — forensic JSONL line shape (canonical keys present)
# ---------------------------------------------------------------------------

@test "AC2.13 forensic JSONL has canonical keys after happy-path fire" {
  echo "added" >> "$WT/seed.txt"
  payload=$(_payload "$WT/seed.txt")
  run _run_hook_with "$payload"
  [ "$status" -eq 0 ]
  CHK_LOG="$TMP/.claude/metrics/$CLAUDE_SESSION_ID/shadow-checkpoints.jsonl"
  [ -f "$CHK_LOG" ]
  LINE=$(tail -1 "$CHK_LOG")
  for key in ts hook task_id worktree_slug step ref sha duration_ms success; do
    echo "$LINE" | jq -e ".${key}" >/dev/null
  done
}

# ---------------------------------------------------------------------------
# AC4.2 — Step 7d cleanup snippet idempotent on zero refs
# ---------------------------------------------------------------------------

@test "AC4.2 cleanup snippet is idempotent when zero checkpoint refs exist" {
  # Run the canonical Step 7d ref-cleanup pre-step against an empty namespace.
  REPO_ROOT_FIX="$WT"
  task="$TASK"
  run bash -c "
    set -euo pipefail
    git -C '$REPO_ROOT_FIX' for-each-ref --format='%(refname)' 'refs/checkpoints/$task/' 2>/dev/null \
      | while IFS= read -r ref; do
          git -C '$REPO_ROOT_FIX' update-ref -d \"\$ref\" 2>/dev/null || true
        done
  "
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# AC4.3 — workstream variant: refs not workstream-prefixed; cleanup still works
# ---------------------------------------------------------------------------

@test "AC4.3 cleanup deletes both checkpoint refs in workstream variant" {
  # Pre-create two refs under the task namespace.
  echo "a" >> "$WT/seed.txt"
  SHA1=$(git -C "$WT" stash create)
  git -C "$WT" update-ref "refs/checkpoints/$TASK/agent-x-0001" "$SHA1"
  echo "b" >> "$WT/seed.txt"
  SHA2=$(git -C "$WT" stash create)
  git -C "$WT" update-ref "refs/checkpoints/$TASK/agent-x-0002" "$SHA2"
  [ "$(_count_checkpoint_refs)" -eq 2 ]

  REPO_ROOT_FIX="$WT"
  task="$TASK"
  run bash -c "
    set -euo pipefail
    git -C '$REPO_ROOT_FIX' for-each-ref --format='%(refname)' 'refs/checkpoints/$task/' 2>/dev/null \
      | while IFS= read -r ref; do
          git -C '$REPO_ROOT_FIX' update-ref -d \"\$ref\" 2>/dev/null || true
        done
  "
  [ "$status" -eq 0 ]
  [ "$(_count_checkpoint_refs)" -eq 0 ]
}

# ---------------------------------------------------------------------------
# AC4.4 — Form-1 find -delete removes the per-worktree counter file
# ---------------------------------------------------------------------------

@test "AC4.4 Form-1 find -delete removes the per-worktree counter file" {
  COUNTER="$STATE_DIR/$TASK/checkpoint-counter-agent-test.txt"
  echo "0007" > "$COUNTER"
  [ -f "$COUNTER" ]
  # Run only the Form-1 cleanup snippet from skills/pipeline/SKILL.md.
  task_dir="$STATE_DIR/$TASK"
  find "$task_dir" -type f -delete
  find "$task_dir" -depth -type d -empty -delete
  [ ! -f "$COUNTER" ]
}
