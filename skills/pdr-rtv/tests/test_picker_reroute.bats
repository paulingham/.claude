#!/usr/bin/env bats
# Security-review F3 — when `_pdr_pick_winner` falls through to the
# diff-stat heuristic placeholder (no test-seam override AND
# CLAUDE_PDR_RTV_LIVE_PICKER unset), the tournament MUST append a
# `## Re-routes` section to `tournament.md` recording that the placeholder
# picker is active. This surfaces the gate-bypass risk to operators in the
# Reflect step and prevents silent diff-stat-only winner selection.

setup() {
  REPO_ROOT="$(cd "${BATS_TEST_DIRNAME}/../../.." && pwd)"
  TOURNAMENT_PATH="$REPO_ROOT/skills/pdr-rtv/lib/tournament.sh"
  TMPROOT="$(mktemp -d)"
  STATE_ROOT="$TMPROOT/state"
  TASK_ID="reroute-test"

  for slug in cand-a cand-b cand-c cand-d; do
    mkdir -p "$STATE_ROOT/$TASK_ID/pdr-rtv/rollouts/$slug"
    cat > "$STATE_ROOT/$TASK_ID/pdr-rtv/rollouts/$slug/summary.md" <<EOF
## Hypotheses Tried
strategy for $slug

## Progress Made
$slug landed core path

## Failure Modes
$slug had edge case
EOF
    printf 'diff_stat=10\nsha=sha-%s\n' "$slug" \
      > "$STATE_ROOT/$TASK_ID/pdr-rtv/rollouts/$slug/meta"
  done

  unset PDR_RTV_TEST_VERDICT_OVERRIDE
  unset CLAUDE_PDR_RTV_LIVE_PICKER
}

teardown() {
  rm -rf "$TMPROOT"
}

@test "F3: placeholder picker emits Re-routes section" {
  # shellcheck source=/dev/null
  source "$TOURNAMENT_PATH"
  command -v run_tournament >/dev/null

  # No override, no live-picker opt-in → placeholder should fire.
  run_tournament \
    --task-id "$TASK_ID" \
    --state-root "$STATE_ROOT" \
    --candidates "cand-a,cand-b,cand-c,cand-d"

  TOURNAMENT_MD="$STATE_ROOT/$TASK_ID/pdr-rtv/tournament.md"
  [ -f "$TOURNAMENT_MD" ]

  # Re-routes section must exist with the placeholder-picker line.
  grep -Fxq "## Re-routes" "$TOURNAMENT_MD"
  grep -Fq "placeholder picker active" "$TOURNAMENT_MD"
  grep -Fq "diff-stat heuristic" "$TOURNAMENT_MD"
}

@test "F3: test override suppresses Re-routes emission" {
  # shellcheck source=/dev/null
  source "$TOURNAMENT_PATH"
  export PDR_RTV_TEST_VERDICT_OVERRIDE="alpha-first"

  run_tournament \
    --task-id "$TASK_ID" \
    --state-root "$STATE_ROOT" \
    --candidates "cand-a,cand-b,cand-c,cand-d"

  TOURNAMENT_MD="$STATE_ROOT/$TASK_ID/pdr-rtv/tournament.md"
  # No re-route emitted under test seam — the override IS the picker.
  ! grep -Fxq "## Re-routes" "$TOURNAMENT_MD"
}

@test "F3: live-picker opt-in suppresses Re-routes emission" {
  # When CLAUDE_PDR_RTV_LIVE_PICKER=1 the orchestrator is asserting
  # patch-critic Agent wiring is live and the lib's diff-stat fallback is
  # only reached as a last-resort tie-breaker. No re-route is emitted.
  # shellcheck source=/dev/null
  source "$TOURNAMENT_PATH"
  export CLAUDE_PDR_RTV_LIVE_PICKER=1

  run_tournament \
    --task-id "$TASK_ID" \
    --state-root "$STATE_ROOT" \
    --candidates "cand-a,cand-b,cand-c,cand-d"

  TOURNAMENT_MD="$STATE_ROOT/$TASK_ID/pdr-rtv/tournament.md"
  ! grep -Fxq "## Re-routes" "$TOURNAMENT_MD"
}
