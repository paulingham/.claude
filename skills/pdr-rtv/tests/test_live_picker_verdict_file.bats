#!/usr/bin/env bats
# AC7 (a/b) — `_pdr_pick_winner` reads the orchestrator-written verdict
# file at `${PDR_RTV_VERDICT_DIR}/<round>-<idx>.verdict` (1-based round
# index, 0-based match index — matches existing `Match ${round_idx}.${match_idx}`
# convention in `_pdr_tournament_md_append_match`) when both
# `CLAUDE_PDR_RTV_LIVE_PICKER=1` AND `PDR_RTV_VERDICT_DIR` are exported.
# Verdict-file format: literal `WINNER: A` or `WINNER: B` on the FIRST
# line (trailing rationale lines are tolerated per patch-critic
# Tournament Mode output spec). On parse success, the chosen slug is
# returned; diff-stat is NOT consulted. Malformed verdict (no first-line
# WINNER:A|B match) → diff-stat fallback with a `parse-failure for
# match {round}.{idx}, fell back to diff-stat` reroute.

setup() {
  REPO_ROOT="$(cd "${BATS_TEST_DIRNAME}/../../.." && pwd)"
  TOURNAMENT_PATH="$REPO_ROOT/skills/pdr-rtv/lib/tournament.sh"
  TMPROOT="$(mktemp -d)"
  STATE_ROOT="$TMPROOT/state"
  VERDICT_DIR="$TMPROOT/verdicts"
  TASK_ID="live-picker-test"
  mkdir -p "$VERDICT_DIR"

  # Two candidates with deliberately asymmetric diff-stats so we can
  # distinguish "verdict-file used" from "diff-stat fallback used".
  # cand-a has SMALLER diff-stat → diff-stat would pick cand-a.
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
  printf 'diff_stat=10\nsha=sha-%s\n' "cand-a" > "$STATE_ROOT/$TASK_ID/pdr-rtv/rollouts/cand-a/meta"
  printf 'diff_stat=99\nsha=sha-%s\n' "cand-b" > "$STATE_ROOT/$TASK_ID/pdr-rtv/rollouts/cand-b/meta"

  unset PDR_RTV_TEST_VERDICT_OVERRIDE
  export CLAUDE_PDR_RTV_LIVE_PICKER=1
  export PDR_RTV_VERDICT_DIR="$VERDICT_DIR"
}

teardown() {
  rm -rf "$TMPROOT"
  unset CLAUDE_PDR_RTV_LIVE_PICKER PDR_RTV_VERDICT_DIR
}

@test "AC7(a): live_picker_reads_verdict_file_and_selects_winner" {
  # Pre-stage verdict file: 1-based round (round 1), 0-based match (match 0).
  # Verdict says WINNER: B — i.e. cand-b should win, despite cand-a having
  # the smaller diff-stat. Trailing rationale line tests parser tolerance:
  # patch-critic may emit a short rationale section after the WINNER line.
  cat > "$VERDICT_DIR/1-0.verdict" <<EOF
WINNER: B
Rationale: cand-b has stronger progress section.
EOF

  # shellcheck source=/dev/null
  source "$TOURNAMENT_PATH"

  run_tournament \
    --task-id "$TASK_ID" \
    --state-root "$STATE_ROOT" \
    --candidates "cand-a,cand-b"

  TOURNAMENT_MD="$STATE_ROOT/$TASK_ID/pdr-rtv/tournament.md"
  [ -f "$TOURNAMENT_MD" ]

  # cand-b wins (verdict-file path), NOT cand-a (diff-stat path).
  grep -Fxq "slug: cand-b" "$TOURNAMENT_MD"
  ! grep -Fxq "slug: cand-a" "$TOURNAMENT_MD"

  # No parse-failure reroute (verdict was well-formed).
  ! grep -Fq "parse-failure for match" "$TOURNAMENT_MD"
}

@test "AC7(b): malformed_verdict_falls_back_to_diff_stat_with_reroute" {
  # Pre-stage MALFORMED verdict file (no first-line `WINNER: A|B`).
  cat > "$VERDICT_DIR/1-0.verdict" <<EOF
something went wrong
WINNER: B
EOF

  # shellcheck source=/dev/null
  source "$TOURNAMENT_PATH"

  run_tournament \
    --task-id "$TASK_ID" \
    --state-root "$STATE_ROOT" \
    --candidates "cand-a,cand-b"

  TOURNAMENT_MD="$STATE_ROOT/$TASK_ID/pdr-rtv/tournament.md"

  # Diff-stat winner (cand-a, smaller diff_stat=10) is selected.
  grep -Fxq "slug: cand-a" "$TOURNAMENT_MD"

  # Reroute records the parse failure with literal match indexing 1.0.
  grep -Fxq "## Re-routes" "$TOURNAMENT_MD"
  grep -Fq "parse-failure for match 1.0, fell back to diff-stat" "$TOURNAMENT_MD"
}
