#!/usr/bin/env bats
# AC3 (a/b) — `_pdr_tournament_md_append_winner` reads the rollout meta
# file. When sha is missing or the meta file does not exist, it writes
# the literal `sha: <unknown>` to `## Winner` AND calls a NEW sibling
# helper `_pdr_tournament_md_append_meta_missing_reroute(slug)` that
# appends `## Re-routes` line `meta-missing for {slug}`. The existing
# F3 zero-arg helper `_pdr_tournament_md_append_reroute()` is NOT
# invoked when meta is missing — only on diff-stat-placeholder firing.
# When meta exists, real sha is emitted and no meta-missing reroute.

setup() {
  REPO_ROOT="$(cd "${BATS_TEST_DIRNAME}/../../.." && pwd)"
  TOURNAMENT_PATH="$REPO_ROOT/skills/pdr-rtv/lib/tournament.sh"
  TMPROOT="$(mktemp -d)"
  STATE_ROOT="$TMPROOT/state"
  TASK_ID="meta-missing-test"

  for slug in cand-a cand-b; do
    mkdir -p "$STATE_ROOT/$TASK_ID/pdr-rtv/rollouts/$slug"
    cat > "$STATE_ROOT/$TASK_ID/pdr-rtv/rollouts/$slug/summary.md" <<EOF
## Hypotheses Tried
strategy for $slug

## Progress Made
$slug landed core path

## Failure Modes
$slug had edge case
EOF
  done

  unset PDR_RTV_TEST_VERDICT_OVERRIDE
  # Use live-picker opt-in to suppress F3 reroute (we want to isolate
  # AC3's meta-missing reroute from the F3 placeholder reroute).
  export CLAUDE_PDR_RTV_LIVE_PICKER=1
}

teardown() {
  rm -rf "$TMPROOT"
  unset CLAUDE_PDR_RTV_LIVE_PICKER
}

@test "AC3(a): winner with missing meta file emits sha unknown and meta-missing reroute via sibling helper" {
  # No meta file is written for either candidate — sha lookup will be empty.
  # shellcheck source=/dev/null
  source "$TOURNAMENT_PATH"

  run_tournament \
    --task-id "$TASK_ID" \
    --state-root "$STATE_ROOT" \
    --candidates "cand-a,cand-b"

  TOURNAMENT_MD="$STATE_ROOT/$TASK_ID/pdr-rtv/tournament.md"
  [ -f "$TOURNAMENT_MD" ]

  # ## Winner section uses the literal `sha: <unknown>` placeholder.
  grep -Fxq "## Winner" "$TOURNAMENT_MD"
  grep -Fxq "sha: <unknown>" "$TOURNAMENT_MD"

  # NEW sibling helper appended a `meta-missing for <winner>` line.
  grep -Eq "^meta-missing for cand-(a|b)$" "$TOURNAMENT_MD"

  # F3 placeholder helper NOT invoked (live-picker is set; placeholder
  # sentinel never fires).
  ! grep -Fq "placeholder picker active" "$TOURNAMENT_MD"
}

@test "AC3(b): winner with valid meta file emits actual sha and no meta-missing reroute" {
  # Stage meta file for both candidates.
  for slug in cand-a cand-b; do
    printf 'diff_stat=10\nsha=sha-%s\n' "$slug" \
      > "$STATE_ROOT/$TASK_ID/pdr-rtv/rollouts/$slug/meta"
  done

  # shellcheck source=/dev/null
  source "$TOURNAMENT_PATH"

  run_tournament \
    --task-id "$TASK_ID" \
    --state-root "$STATE_ROOT" \
    --candidates "cand-a,cand-b"

  TOURNAMENT_MD="$STATE_ROOT/$TASK_ID/pdr-rtv/tournament.md"

  # Real sha emitted (one of sha-cand-a or sha-cand-b).
  grep -Eq '^sha: sha-cand-(a|b)$' "$TOURNAMENT_MD"

  # No meta-missing reroute fires when meta is present.
  ! grep -Fq "meta-missing for" "$TOURNAMENT_MD"
  ! grep -Fxq "sha: <unknown>" "$TOURNAMENT_MD"
}
