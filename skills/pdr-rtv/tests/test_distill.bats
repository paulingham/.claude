#!/usr/bin/env bats
# AC2 — `lib/distill.sh` exposes a sourceable `distill_rollout` function.
# The summary lives at pipeline-state/{task-id}/pdr-rtv/rollouts/{slug}/summary.md
# (OUTSIDE the worktree so worktree reaping is safe), has exactly three
# required H2 sections, and is ≤2KB.

setup() {
  REPO_ROOT="$(cd "${BATS_TEST_DIRNAME}/../../.." && pwd)"
  LIB_PATH="$REPO_ROOT/skills/pdr-rtv/lib/distill.sh"
  TMPROOT="$(mktemp -d)"
  WORKTREE="$TMPROOT/worktree"
  STATE_ROOT="$TMPROOT/state"
  TASK_ID="distill-test-task"
  SLUG="cand-alpha"
  mkdir -p "$WORKTREE" "$STATE_ROOT"

  # Minimal worktree fixture: a couple of source files + a commit message
  # carrying the [SUMMARY] block the build engineer prepended.
  echo "fn main() { }" > "$WORKTREE/main.rs"
  cat > "$WORKTREE/COMMIT_MSG" <<'EOF'
[SUMMARY]
HYPOTHESES: tried strategy A, then strategy B
PROGRESS: implemented core path
FAILURES: edge case on empty input remained
[/SUMMARY]

Rollout summary commit.
EOF
}

teardown() {
  rm -rf "$TMPROOT"
}

@test "AC2: distill_writes_three_sections" {
  [ -f "$LIB_PATH" ]
  # shellcheck source=/dev/null
  source "$LIB_PATH"

  # Function is exposed and sourceable.
  command -v distill_rollout >/dev/null

  # Call signature: distill_rollout <worktree> <state_root> <task_id> <slug>
  run distill_rollout "$WORKTREE" "$STATE_ROOT" "$TASK_ID" "$SLUG"
  [ "$status" -eq 0 ]

  SUMMARY="$STATE_ROOT/$TASK_ID/pdr-rtv/rollouts/$SLUG/summary.md"
  [ -f "$SUMMARY" ]

  # Summary persists OUTSIDE worktree (load-bearing for reap safety).
  case "$SUMMARY" in
    "$WORKTREE"/*) return 1 ;;
  esac

  # Exactly three required H2 sections (case-sensitive, exact line match).
  grep -Fxq "## Hypotheses Tried" "$SUMMARY"
  grep -Fxq "## Progress Made" "$SUMMARY"
  grep -Fxq "## Failure Modes" "$SUMMARY"

  # ≤2KB cap.
  size="$(wc -c <"$SUMMARY" | tr -d ' ')"
  [ "$size" -le 2048 ]
}
