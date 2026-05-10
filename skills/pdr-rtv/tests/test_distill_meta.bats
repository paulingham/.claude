#!/usr/bin/env bats
# AC1 (a/b) — `distill_rollout` writes a `meta` file alongside `summary.md`
# carrying `sha=<git rev-parse HEAD>` and `diff_stat=<line count of git diff
# --shortstat HEAD~1..HEAD>`. When no commit at HEAD (empty repo), distill
# fails-loud: exit code 2, stderr contains `cannot derive meta`. Closes a
# silent-empty-sha bug surfaced by security review of PR #104.

setup() {
  REPO_ROOT="$(cd "${BATS_TEST_DIRNAME}/../../.." && pwd)"
  DISTILL_PATH="$REPO_ROOT/skills/pdr-rtv/lib/distill.sh"
  TMPROOT="$(mktemp -d)"
  WORKTREE="$TMPROOT/worktree"
  STATE_ROOT="$TMPROOT/state"
  TASK_ID="distill-meta-test"
  SLUG="cand-meta"
  mkdir -p "$WORKTREE" "$STATE_ROOT"
}

teardown() {
  rm -rf "$TMPROOT"
}

_seed_commit_with_summary() {
  # Initialise a worktree with a single commit that includes a [SUMMARY] block.
  ( cd "$WORKTREE" \
      && git init -q \
      && git config user.email t@t.t \
      && git config user.name "t" \
      && echo "fn main(){}" > main.rs \
      && git add main.rs \
      && git commit -q -m "$(printf '[SUMMARY]\nHYPOTHESES: tried strategy A\nPROGRESS: pushed core path\nFAILURES: edge case remained\n[/SUMMARY]\n\nrollout commit')" )
}

@test "AC1(a): distill_rollout writes meta file with sha and diff_stat" {
  _seed_commit_with_summary
  EXPECTED_SHA="$(git -C "$WORKTREE" rev-parse HEAD)"

  # shellcheck source=/dev/null
  source "$DISTILL_PATH"

  run distill_rollout "$WORKTREE" "$STATE_ROOT" "$TASK_ID" "$SLUG"
  [ "$status" -eq 0 ]

  META="$STATE_ROOT/$TASK_ID/pdr-rtv/rollouts/$SLUG/meta"
  [ -f "$META" ]

  # sha line is the actual HEAD sha.
  grep -Fxq "sha=${EXPECTED_SHA}" "$META"

  # diff_stat is an integer (line count of git diff --shortstat HEAD~1..HEAD).
  grep -Eq '^diff_stat=[0-9]+$' "$META"

  # Summary still exists alongside.
  [ -f "$STATE_ROOT/$TASK_ID/pdr-rtv/rollouts/$SLUG/summary.md" ]
}

@test "AC1(b): distill_rollout exits non-zero when worktree has no commit at HEAD" {
  # Empty git repo — git rev-parse --verify HEAD will fail.
  ( cd "$WORKTREE" && git init -q && git config user.email t@t.t && git config user.name "t" )

  # shellcheck source=/dev/null
  source "$DISTILL_PATH"

  run distill_rollout "$WORKTREE" "$STATE_ROOT" "$TASK_ID" "$SLUG"
  [ "$status" -eq 2 ]
  # bats default `run` puts stderr+stdout into $output. `[[ ]]` returning
  # 1 does NOT abort the test under bats 1.13, so we force failure with `|| false`.
  [[ "$output" == *"cannot derive meta"* ]] || false
}
