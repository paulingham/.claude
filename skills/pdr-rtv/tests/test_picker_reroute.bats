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

@test "AC2: live-picker opt-in does not touch placeholder sentinel even on diff-stat tie-break" {
  # Round 2 of the AC2 contract — when CLAUDE_PDR_RTV_LIVE_PICKER=1 is
  # set AND `_pdr_pick_winner_by_diff_stat` runs (no verdict file
  # available, falls through to tie-breaker), the placeholder sentinel
  # MUST NOT be touched. tournament.md therefore contains no
  # `placeholder picker active` line.
  # shellcheck source=/dev/null
  source "$TOURNAMENT_PATH"
  export CLAUDE_PDR_RTV_LIVE_PICKER=1
  unset PDR_RTV_VERDICT_DIR

  run_tournament \
    --task-id "$TASK_ID" \
    --state-root "$STATE_ROOT" \
    --candidates "cand-a,cand-b,cand-c,cand-d"

  TOURNAMENT_MD="$STATE_ROOT/$TASK_ID/pdr-rtv/tournament.md"
  ! grep -Fq "placeholder picker active" "$TOURNAMENT_MD"
}

@test "AC2-bis: live-picker-flag-missing emits reroute and stderr warning when env unset in production" {
  # When CLAUDE_PDR_RTV_LIVE_PICKER and PDR_RTV_TEST_VERDICT_OVERRIDE
  # are BOTH unset (production without flag), `run_tournament` emits a
  # stderr warning AND adds a `## Re-routes` line
  # `live-picker-flag-missing — operator must export
  # CLAUDE_PDR_RTV_LIVE_PICKER=1`. Cause-then-symptom convention: the
  # AC2-bis line MUST appear BEFORE the F3 `placeholder picker active`
  # line under the shared `## Re-routes` header.
  # shellcheck source=/dev/null
  source "$TOURNAMENT_PATH"

  unset PDR_RTV_TEST_VERDICT_OVERRIDE
  unset CLAUDE_PDR_RTV_LIVE_PICKER

  bats_require_minimum_version 1.5.0
  run --separate-stderr run_tournament \
    --task-id "$TASK_ID" \
    --state-root "$STATE_ROOT" \
    --candidates "cand-a,cand-b,cand-c,cand-d"
  [ "$status" -eq 0 ]
  # `run --separate-stderr` puts stderr into $stderr and stdout into $output.
  # AC2-bis demands stderr warning explicitly (operator-facing surface).
  # Assert with explicit `|| false` — bats 1.13's default test mode does
  # not abort on a `[[ ]]` returning 1, so we force the failure path.
  [[ "$stderr" == *"live-picker-flag-missing"* ]] || false

  TOURNAMENT_MD="$STATE_ROOT/$TASK_ID/pdr-rtv/tournament.md"
  [ -f "$TOURNAMENT_MD" ]

  # Reroute header + AC2-bis line + F3 line all present.
  grep -Fxq "## Re-routes" "$TOURNAMENT_MD"
  grep -Fq "live-picker-flag-missing — operator must export CLAUDE_PDR_RTV_LIVE_PICKER=1" "$TOURNAMENT_MD"
  grep -Fq "placeholder picker active" "$TOURNAMENT_MD"

  # Ordering: AC2-bis line BEFORE F3 line (cause-then-symptom).
  reroute_section="$(awk '/## Re-routes/,0' "$TOURNAMENT_MD")"
  ac2bis_line_no="$(echo "$reroute_section" | grep -n "live-picker-flag-missing" | head -1 | cut -d: -f1)"
  f3_line_no="$(echo "$reroute_section" | grep -n "placeholder picker active" | head -1 | cut -d: -f1)"
  [ -n "$ac2bis_line_no" ]
  [ -n "$f3_line_no" ]
  [ "$ac2bis_line_no" -lt "$f3_line_no" ]
}
