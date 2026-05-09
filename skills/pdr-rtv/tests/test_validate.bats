#!/usr/bin/env bats
# Security-review F1 — `lib/validate.sh` exposes `_pdr_validate_task_id` and
# `_pdr_validate_slug`. Both functions reject identifiers that would escape
# the pipeline-state directory via path-traversal characters (`..`, `/`,
# leading `.`, empty) and accept the standard `[a-zA-Z0-9_.-]+` shape.
#
# F2 piggyback — `reap_iteration_0_worktrees` invokes the slug validator on
# every prior-summary directory entry; malformed slugs are skipped, not
# emitted as `WORKTREE_CLOSE` events.

setup() {
  REPO_ROOT="$(cd "${BATS_TEST_DIRNAME}/../../.." && pwd)"
  VALIDATE_PATH="$REPO_ROOT/skills/pdr-rtv/lib/validate.sh"
  DISPATCH_PATH="$REPO_ROOT/skills/pdr-rtv/lib/dispatch.sh"
  DISTILL_PATH="$REPO_ROOT/skills/pdr-rtv/lib/distill.sh"
  TOURNAMENT_PATH="$REPO_ROOT/skills/pdr-rtv/lib/tournament.sh"
  TMPROOT="$(mktemp -d)"
  STATE_ROOT="$TMPROOT/state"
  mkdir -p "$STATE_ROOT"
}

teardown() {
  rm -rf "$TMPROOT"
}

@test "F1: validate.sh exposes both validators" {
  [ -f "$VALIDATE_PATH" ]
  # shellcheck source=/dev/null
  source "$VALIDATE_PATH"
  command -v _pdr_validate_task_id >/dev/null
  command -v _pdr_validate_slug >/dev/null
}

@test "F1: task_id validator accepts standard identifiers" {
  # shellcheck source=/dev/null
  source "$VALIDATE_PATH"
  _pdr_validate_task_id "my-task-1"
  _pdr_validate_task_id "task_abc.def"
  _pdr_validate_task_id "PDR-RTV-skill"
}

@test "F1: task_id validator rejects path traversal" {
  # shellcheck source=/dev/null
  source "$VALIDATE_PATH"
  ! _pdr_validate_task_id "../etc/passwd" 2>/dev/null
  ! _pdr_validate_task_id "task/../etc" 2>/dev/null
  ! _pdr_validate_task_id ".hidden" 2>/dev/null
  ! _pdr_validate_task_id "foo..bar" 2>/dev/null
}

@test "F1: task_id validator rejects empty and slash-bearing inputs" {
  # shellcheck source=/dev/null
  source "$VALIDATE_PATH"
  ! _pdr_validate_task_id "" 2>/dev/null
  ! _pdr_validate_task_id "with/slash" 2>/dev/null
  ! _pdr_validate_task_id "with space" 2>/dev/null
  ! _pdr_validate_task_id "with;semi" 2>/dev/null
}

@test "F1: slug validator has the same shape as task_id" {
  # shellcheck source=/dev/null
  source "$VALIDATE_PATH"
  _pdr_validate_slug "iter1-alpha"
  _pdr_validate_slug "cand_a.b"
  ! _pdr_validate_slug "../bad" 2>/dev/null
  ! _pdr_validate_slug "" 2>/dev/null
  ! _pdr_validate_slug "slug/with/slash" 2>/dev/null
  ! _pdr_validate_slug "..foo" 2>/dev/null
}

@test "F1: dispatch_iteration rejects malformed task_id" {
  # shellcheck source=/dev/null
  source "$DISPATCH_PATH"
  run dispatch_iteration 0 \
    --task-id "../escape" \
    --state-root "$STATE_ROOT" \
    --candidates "iter0-a,iter0-b"
  [ "$status" -ne 0 ]
}

@test "F1: dispatch_iteration rejects malformed candidate slug" {
  # shellcheck source=/dev/null
  source "$DISPATCH_PATH"
  run dispatch_iteration 0 \
    --task-id "good-task" \
    --state-root "$STATE_ROOT" \
    --candidates "good-a,../escape"
  [ "$status" -ne 0 ]
}

@test "F1: distill_rollout rejects malformed task_id" {
  # shellcheck source=/dev/null
  source "$DISTILL_PATH"
  WT="$TMPROOT/worktree"
  mkdir -p "$WT"
  echo "[SUMMARY]" > "$WT/COMMIT_MSG"
  echo "[/SUMMARY]" >> "$WT/COMMIT_MSG"
  run distill_rollout "$WT" "$STATE_ROOT" "../escape" "good-slug"
  [ "$status" -ne 0 ]
}

@test "F1: distill_rollout rejects malformed slug" {
  # shellcheck source=/dev/null
  source "$DISTILL_PATH"
  WT="$TMPROOT/worktree"
  mkdir -p "$WT"
  echo "[SUMMARY]" > "$WT/COMMIT_MSG"
  echo "[/SUMMARY]" >> "$WT/COMMIT_MSG"
  run distill_rollout "$WT" "$STATE_ROOT" "good-task" "../escape"
  [ "$status" -ne 0 ]
}

@test "F1: run_tournament rejects malformed task_id" {
  # shellcheck source=/dev/null
  source "$TOURNAMENT_PATH"
  run run_tournament \
    --task-id "../escape" \
    --state-root "$STATE_ROOT" \
    --candidates "cand-a,cand-b"
  [ "$status" -ne 0 ]
}

@test "F1: run_tournament rejects malformed candidate slug" {
  # shellcheck source=/dev/null
  source "$TOURNAMENT_PATH"
  run run_tournament \
    --task-id "good-task" \
    --state-root "$STATE_ROOT" \
    --candidates "good-a,../escape"
  [ "$status" -ne 0 ]
}

@test "F2: reap_iteration_0_worktrees skips malformed slug directories" {
  # shellcheck source=/dev/null
  source "$DISPATCH_PATH"
  TASK_ID="reap-validate"
  ROLLOUTS="$STATE_ROOT/$TASK_ID/pdr-rtv/rollouts"
  mkdir -p "$ROLLOUTS"
  # One legitimate, one malformed (filesystem-allowed but slug-invalid).
  for slug in "good-slug" "..hidden"; do
    mkdir -p "$ROLLOUTS/$slug"
    echo "## Hypotheses Tried" > "$ROLLOUTS/$slug/summary.md"
  done

  WORKTREE_LOG="$TMPROOT/wt-events.log"
  : > "$WORKTREE_LOG"
  export PDR_RTV_TEST_WORKTREE_LOG="$WORKTREE_LOG"

  reap_iteration_0_worktrees \
    --task-id "$TASK_ID" \
    --state-root "$STATE_ROOT"

  # Only the good slug should appear in the close events. Use grep + wc to
  # avoid the `grep -c ... || echo 0` two-line trap (grep exits non-zero on
  # zero matches, the fallback then appends a second line).
  good_count="$(grep -F 'slug=good-slug' "$WORKTREE_LOG" 2>/dev/null | wc -l | tr -d ' ')"
  bad_count="$(grep -F 'slug=..hidden' "$WORKTREE_LOG" 2>/dev/null | wc -l | tr -d ' ')"
  [ "$good_count" -eq 1 ]
  [ "$bad_count" -eq 0 ]
}
