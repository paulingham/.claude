#!/usr/bin/env bats
# AC3, AC3-bis, AC4 — `lib/dispatch.sh` exposes `dispatch_iteration` and
# `reap_iteration_0_worktrees`. Iteration ≥ 1 injects K=2 randomly-sampled
# prior-iteration summaries into spawn prompts under
# `## Refine From Prior Attempts`. Iterations strictly serialise so peak
# concurrent worktrees == N (=4), not 2N. CLAUDE_PDR_SEED makes the
# sampling deterministic.

setup() {
  REPO_ROOT="$(cd "${BATS_TEST_DIRNAME}/../../.." && pwd)"
  DISPATCH_PATH="$REPO_ROOT/skills/pdr-rtv/lib/dispatch.sh"
  TMPROOT="$(mktemp -d)"
  STATE_ROOT="$TMPROOT/state"
  TASK_ID="dispatch-test-task"
  PROMPT_LOG="$TMPROOT/spawn-prompts.log"
  WORKTREE_LOG="$TMPROOT/worktree-events.log"

  mkdir -p "$STATE_ROOT/$TASK_ID/pdr-rtv/rollouts"

  # Pre-populate iteration-0 summaries (4 candidates).
  for slug in iter0-alpha iter0-beta iter0-gamma iter0-delta; do
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

  # Stub Agent dispatcher: just record the prompt rendering decisions.
  export PDR_RTV_TEST_PROMPT_LOG="$PROMPT_LOG"
  export PDR_RTV_TEST_WORKTREE_LOG="$WORKTREE_LOG"
  : > "$PROMPT_LOG"
  : > "$WORKTREE_LOG"
}

teardown() {
  rm -rf "$TMPROOT"
}

@test "AC3: iteration_1_injects_two_prior_summaries" {
  [ -f "$DISPATCH_PATH" ]
  # shellcheck source=/dev/null
  source "$DISPATCH_PATH"
  command -v dispatch_iteration >/dev/null

  CLAUDE_PDR_SEED=42 dispatch_iteration 1 \
    --task-id "$TASK_ID" \
    --state-root "$STATE_ROOT" \
    --candidates "iter1-a,iter1-b,iter1-c,iter1-d"

  # Each of the 4 spawn prompts must contain the section header AND
  # exactly 2 prior-summary blocks.
  candidate_count="$(grep -c '^CANDIDATE:' "$PROMPT_LOG" || echo 0)"
  [ "$candidate_count" -eq 4 ]

  # For every candidate's prompt, count the "## Refine From Prior Attempts"
  # section and the SUMMARY-BLOCK markers under it.
  while IFS= read -r prompt_file; do
    grep -Fxq "## Refine From Prior Attempts" "$prompt_file"
    block_count="$(grep -c '^### Prior Attempt:' "$prompt_file")"
    [ "$block_count" -eq 2 ]
  done < <(find "$TMPROOT" -type f -name 'prompt-iter1-*.txt')
}

@test "AC3-bis: iterations_strictly_serialise_worktree_count_drops_to_baseline" {
  # shellcheck source=/dev/null
  source "$DISPATCH_PATH"
  command -v dispatch_iteration >/dev/null
  command -v reap_iteration_0_worktrees >/dev/null

  # Driver simulates the canonical sequence: dispatch_iter0, reap, dispatch_iter1.
  # Each dispatch_iteration logs "WORKTREE_OPEN <slug>" / "WORKTREE_CLOSE <slug>"
  # to $PDR_RTV_TEST_WORKTREE_LOG; the reap function logs one CLOSE per iter-0
  # candidate. We assert peak open count == N (4), never 2N (8).

  CLAUDE_PDR_SEED=42 dispatch_iteration 0 \
    --task-id "$TASK_ID" \
    --state-root "$STATE_ROOT" \
    --candidates "iter0-alpha,iter0-beta,iter0-gamma,iter0-delta"

  # After iter-0 dispatch + before reap, peak = 4.
  peak_before_reap="$(_pdr_peak_open_count "$WORKTREE_LOG")"
  [ "$peak_before_reap" -eq 4 ]

  reap_iteration_0_worktrees \
    --task-id "$TASK_ID" \
    --state-root "$STATE_ROOT"

  # After reap, current open == 0.
  open_after_reap="$(_pdr_current_open_count "$WORKTREE_LOG")"
  [ "$open_after_reap" -eq 0 ]

  CLAUDE_PDR_SEED=42 dispatch_iteration 1 \
    --task-id "$TASK_ID" \
    --state-root "$STATE_ROOT" \
    --candidates "iter1-a,iter1-b,iter1-c,iter1-d"

  # Peak across the entire run never exceeds N=4 (strict serialisation).
  global_peak="$(_pdr_peak_open_count "$WORKTREE_LOG")"
  [ "$global_peak" -eq 4 ]

  # Final state: every iter-1 worktree was closed too (open count == 0).
  open_after_iter1="$(_pdr_current_open_count "$WORKTREE_LOG")"
  [ "$open_after_iter1" -eq 0 ]
}

# Helper: peak count of OPEN-CLOSE balance in the log.
_pdr_peak_open_count() {
  awk '
    /^WORKTREE_OPEN/  { open++; if (open > peak) peak = open }
    /^WORKTREE_CLOSE/ { open-- }
    END { print peak }
  ' "$1"
}

_pdr_current_open_count() {
  awk '
    /^WORKTREE_OPEN/  { open++ }
    /^WORKTREE_CLOSE/ { open-- }
    END { print open }
  ' "$1"
}

@test "AC4-carryforward: seed_subkey_drives_per_candidate_divergence" {
  # Slice 1 reviewer INFO-3 (regression-prevention test). The current
  # `_pdr_seed_int` implementation passes the candidate slug as a sub-key
  # so each candidate gets a distinct shuffle. AC4's existing test only
  # asserts same-seed determinism — it does NOT catch a refactor that
  # drops the subkey, which would silently collapse all N candidates to
  # the same prior pair, killing the diversity PDR exists to capture.
  # This test fails IFF the subkey is removed; it passes today (defends
  # the working behaviour from future mutations).

  # shellcheck source=/dev/null
  source "$DISPATCH_PATH"
  command -v dispatch_iteration >/dev/null

  CLAUDE_PDR_SEED=42 dispatch_iteration 1 \
    --task-id "$TASK_ID" \
    --state-root "$STATE_ROOT" \
    --candidates "iter1-a,iter1-b,iter1-c,iter1-d"

  # Extract the prior-attempt slugs from each candidate's prompt and assert
  # at least 2 distinct candidates have different prior pairs (proves the
  # subkey is load-bearing). Bash 3.2-compatible (no `declare -A`): emit one
  # line per candidate and count uniques across all 4 prompts.
  signatures_file="$TMPROOT/per-candidate-pair-signatures.txt"
  : > "$signatures_file"
  while IFS= read -r prompt_file; do
    sig="$(grep '^### Prior Attempt:' "$prompt_file" | sort | tr '\n' '|')"
    printf '%s\n' "$sig" >> "$signatures_file"
  done < <(find "$TMPROOT" -type f -name 'prompt-iter1-*.txt')

  distinct_count="$(sort -u "$signatures_file" | wc -l | tr -d ' ')"
  # With N=4 candidates and 4 prior summaries, we expect >=2 distinct pairs.
  # All 4 identical would mean the subkey was dropped — the contract violation.
  [ "$distinct_count" -ge 2 ]
}

@test "AC4: seed_makes_summary_sampling_deterministic" {
  # shellcheck source=/dev/null
  source "$DISPATCH_PATH"

  CLAUDE_PDR_SEED=42 dispatch_iteration 1 \
    --task-id "$TASK_ID" \
    --state-root "$STATE_ROOT" \
    --candidates "iter1-x,iter1-y,iter1-z,iter1-w"

  RUN1_DIGEST="$(find "$TMPROOT" -type f -name 'prompt-iter1-*.txt' \
                 -exec sha256sum {} \; | awk '{print $1}' | sort | sha256sum)"

  # Reset prompt artifacts between runs.
  find "$TMPROOT" -type f -name 'prompt-iter1-*.txt' -delete
  : > "$PROMPT_LOG"
  : > "$WORKTREE_LOG"

  CLAUDE_PDR_SEED=42 dispatch_iteration 1 \
    --task-id "$TASK_ID" \
    --state-root "$STATE_ROOT" \
    --candidates "iter1-x,iter1-y,iter1-z,iter1-w"

  RUN2_DIGEST="$(find "$TMPROOT" -type f -name 'prompt-iter1-*.txt' \
                 -exec sha256sum {} \; | awk '{print $1}' | sort | sha256sum)"

  [ "$RUN1_DIGEST" = "$RUN2_DIGEST" ]
}
