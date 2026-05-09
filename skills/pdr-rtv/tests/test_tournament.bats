#!/usr/bin/env bats
# AC5, AC6, AC7 — `lib/tournament.sh` exposes `run_tournament` running
# single-elimination pairwise comparison over candidate slugs. Comparisons
# spawn `patch-critic` with `Mode: tournament` and `Candidates: A,B`
# tokens; verdicts are binary `WINNER: A|B`. Tournament writes
# `pipeline-state/{task-id}/pdr-rtv/tournament.md` with frontmatter,
# every round, and a `## Winner` section.
#
# Test seam: PDR_RTV_TEST_TOURNAMENT_LOG (records every comparison spawn) +
# PDR_RTV_TEST_VERDICT_OVERRIDE (deterministic winner-picking for tests).

setup() {
  REPO_ROOT="$(cd "${BATS_TEST_DIRNAME}/../../.." && pwd)"
  TOURNAMENT_PATH="$REPO_ROOT/skills/pdr-rtv/lib/tournament.sh"
  TMPROOT="$(mktemp -d)"
  STATE_ROOT="$TMPROOT/state"
  TASK_ID="tournament-test-task"
  TOURNAMENT_LOG="$TMPROOT/tournament-events.log"

  # Stage 8 candidate summaries with deterministic content + diff sizes.
  for slug in cand-a cand-b cand-c cand-d cand-e cand-f cand-g cand-h; do
    mkdir -p "$STATE_ROOT/$TASK_ID/pdr-rtv/rollouts/$slug"
    cat > "$STATE_ROOT/$TASK_ID/pdr-rtv/rollouts/$slug/summary.md" <<EOF
## Hypotheses Tried
strategy for $slug

## Progress Made
$slug landed core path

## Failure Modes
$slug had edge case
EOF
    # Diff stats sidecar (used by tie-breaker rule per AC6 spec).
    echo "diff_stat=42" > "$STATE_ROOT/$TASK_ID/pdr-rtv/rollouts/$slug/meta"
    echo "sha=sha-$slug" >> "$STATE_ROOT/$TASK_ID/pdr-rtv/rollouts/$slug/meta"
  done

  export PDR_RTV_TEST_TOURNAMENT_LOG="$TOURNAMENT_LOG"
  : > "$TOURNAMENT_LOG"
}

teardown() {
  rm -rf "$TMPROOT"
}

@test "AC5: run_tournament_8_candidates_3_rounds" {
  [ -f "$TOURNAMENT_PATH" ]
  # shellcheck source=/dev/null
  source "$TOURNAMENT_PATH"
  command -v run_tournament >/dev/null

  # Deterministic verdicts: with this override, each comparison picks the
  # candidate whose slug sorts FIRST alphabetically. With 8 candidates
  # cand-a..cand-h, single-elimination would produce 7 comparisons.
  export PDR_RTV_TEST_VERDICT_OVERRIDE="alpha-first"

  run_tournament \
    --task-id "$TASK_ID" \
    --state-root "$STATE_ROOT" \
    --candidates "cand-a,cand-b,cand-c,cand-d,cand-e,cand-f,cand-g,cand-h"

  comparison_count="$(grep -c '^COMPARE ' "$TOURNAMENT_LOG")"
  [ "$comparison_count" -eq 7 ]

  winner_count="$(grep -c '^WINNER ' "$TOURNAMENT_LOG")"
  [ "$winner_count" -eq 1 ]
}

@test "AC6: comparison_spawns_patch_critic_tournament_mode" {
  # shellcheck source=/dev/null
  source "$TOURNAMENT_PATH"
  command -v run_tournament >/dev/null

  export PDR_RTV_TEST_VERDICT_OVERRIDE="alpha-first"

  run_tournament \
    --task-id "$TASK_ID" \
    --state-root "$STATE_ROOT" \
    --candidates "cand-a,cand-b,cand-c,cand-d"

  # Each COMPARE line carries a prompt-file reference. Each prompt MUST contain
  # subagent_type=patch-critic, Mode: tournament, and Candidates: A,B.
  comparison_count="$(grep -c '^COMPARE ' "$TOURNAMENT_LOG")"
  [ "$comparison_count" -eq 3 ]  # 4 → 2 → 1

  while IFS= read -r prompt_file; do
    grep -Fxq "subagent_type: patch-critic" "$prompt_file"
    grep -Fxq "Mode: tournament" "$prompt_file"
    grep -Eq "^Candidates: [a-z-]+,[a-z-]+$" "$prompt_file"
  done < <(find "$TMPROOT" -type f -name 'comparison-*.txt')
}

@test "AC6-tiebreak: smaller_diff_stat_wins_when_no_test_override" {
  # Production tie-breaker rule (rubric §§ 1–4 ties → smaller diff-stat).
  # Override slug-meta files so cand-c has the smallest diff_stat, then run
  # without the alpha-first verdict override — picker MUST select cand-c
  # despite alphabetical first being cand-a.
  # shellcheck source=/dev/null
  source "$TOURNAMENT_PATH"

  # Override diff_stat — cand-c smallest.
  for slug in cand-a cand-b cand-c cand-d; do
    case "$slug" in
      cand-c) printf 'diff_stat=10\nsha=sha-%s\n' "$slug" > "$STATE_ROOT/$TASK_ID/pdr-rtv/rollouts/$slug/meta" ;;
      *)      printf 'diff_stat=99\nsha=sha-%s\n' "$slug" > "$STATE_ROOT/$TASK_ID/pdr-rtv/rollouts/$slug/meta" ;;
    esac
  done

  unset PDR_RTV_TEST_VERDICT_OVERRIDE

  run_tournament \
    --task-id "$TASK_ID" \
    --state-root "$STATE_ROOT" \
    --candidates "cand-a,cand-b,cand-c,cand-d"

  TOURNAMENT_MD="$STATE_ROOT/$TASK_ID/pdr-rtv/tournament.md"
  grep -Fxq "slug: cand-c" "$TOURNAMENT_MD"
}

@test "AC7: tournament_md_records_full_bracket" {
  # shellcheck source=/dev/null
  source "$TOURNAMENT_PATH"
  command -v run_tournament >/dev/null

  export PDR_RTV_TEST_VERDICT_OVERRIDE="alpha-first"

  run_tournament \
    --task-id "$TASK_ID" \
    --state-root "$STATE_ROOT" \
    --candidates "cand-a,cand-b,cand-c,cand-d"

  TOURNAMENT_MD="$STATE_ROOT/$TASK_ID/pdr-rtv/tournament.md"
  [ -f "$TOURNAMENT_MD" ]

  # Frontmatter requirements
  grep -Fxq "task_id: $TASK_ID" "$TOURNAMENT_MD"
  grep -Fxq "phase: build" "$TOURNAMENT_MD"
  grep -Fxq "mode: tournament" "$TOURNAMENT_MD"

  # N-1 round entries (4 candidates → 3 matches)
  match_count="$(grep -c '^### Match ' "$TOURNAMENT_MD")"
  [ "$match_count" -eq 3 ]

  # Final winner section with slug + SHA. Under "alpha-first" override the
  # winner of the alphabetic bracket cand-a..cand-d is exactly cand-a.
  grep -Fxq "## Winner" "$TOURNAMENT_MD"
  grep -Fxq "slug: cand-a" "$TOURNAMENT_MD"
  grep -Fxq "sha: sha-cand-a" "$TOURNAMENT_MD"
}
