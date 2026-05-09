#!/usr/bin/env bash
# dispatch.sh — pdr-rtv iteration dispatch + worktree reaping helpers.
#
# Public functions:
#   dispatch_iteration <iter> --task-id ID --state-root DIR --candidates a,b,c,d
#       Spawns N parallel build engineers for iteration <iter>. For
#       iteration >= 1 it samples K=2 prior-iteration summaries (deterministic
#       under CLAUDE_PDR_SEED) and injects them into each engineer's spawn
#       prompt under a `## Refine From Prior Attempts` section.
#
#   reap_iteration_0_worktrees --task-id ID --state-root DIR
#       Closes every iteration-0 worktree AFTER its summary.md has been
#       persisted to <state_root>/<task_id>/pdr-rtv/rollouts/<slug>/.
#       Mirrors the contract documented in AC3-bis: peak concurrent
#       worktree count = N (=4), never 2N.
#
# Test seam: when PDR_RTV_TEST_PROMPT_LOG / PDR_RTV_TEST_WORKTREE_LOG are
# set, the dispatcher records spawn prompts and worktree open/close events
# instead of calling the real Agent tool. This is the substitution point
# tests use to assert behaviour without spawning real subagents.

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

_pdr_parse_kv_args() {
  # Populates _PDR_TASK_ID, _PDR_STATE_ROOT, _PDR_CANDIDATES (CSV string).
  _PDR_TASK_ID=""
  _PDR_STATE_ROOT=""
  _PDR_CANDIDATES=""
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --task-id)     _PDR_TASK_ID="$2";    shift 2 ;;
      --state-root)  _PDR_STATE_ROOT="$2"; shift 2 ;;
      --candidates)  _PDR_CANDIDATES="$2"; shift 2 ;;
      *) echo "dispatch_iteration: unknown flag: $1" >&2; return 2 ;;
    esac
  done
  [ -n "$_PDR_TASK_ID" ]    || { echo "dispatch_iteration: --task-id required" >&2; return 2; }
  [ -n "$_PDR_STATE_ROOT" ] || { echo "dispatch_iteration: --state-root required" >&2; return 2; }
  [ -n "$_PDR_CANDIDATES" ] || { echo "dispatch_iteration: --candidates required" >&2; return 2; }
}

# ---------------------------------------------------------------------------
# Deterministic prior-summary sampling
# ---------------------------------------------------------------------------
#
# Given a deterministic seed and a stable list of candidate slugs, return
# K=2 distinct slugs picked from the prior-iteration summary directory.
# Determinism comes from awk's srand(seed_int) — the same seed + same input
# yields the same shuffle.

_pdr_list_prior_summary_slugs() {
  # Lists slugs (basenames of subdirectories) under
  # <state_root>/<task_id>/pdr-rtv/rollouts/ that contain a summary.md file.
  local state_root="$1" task_id="$2"
  local base="${state_root}/${task_id}/pdr-rtv/rollouts"
  [ -d "$base" ] || return 0
  ( cd "$base" && \
    for d in */; do
      [ -f "$d/summary.md" ] && printf '%s\n' "${d%/}"
    done | sort )
}

_pdr_seed_int() {
  # Maps CLAUDE_PDR_SEED (free-form string) + per-candidate sub-key to a
  # stable integer for awk's srand. Empty seed → 0.
  local raw="${CLAUDE_PDR_SEED:-0}" subkey="${1:-}"
  printf '%s|%s' "$raw" "$subkey" \
    | cksum | awk '{print $1}'
}

_pdr_sample_two_prior_summaries() {
  # Args: <state_root> <task_id> <candidate_slug>
  # Emits the two chosen slugs on stdout, one per line, deterministic.
  local state_root="$1" task_id="$2" cand="$3"
  local seed_int
  seed_int="$(_pdr_seed_int "$cand")"
  _pdr_list_prior_summary_slugs "$state_root" "$task_id" | \
    awk -v s="$seed_int" '
      BEGIN { srand(s) }
      { lines[NR] = $0 }
      END {
        n = NR
        if (n == 0) exit
        # Fisher-Yates partial shuffle: pick first two.
        for (i = 1; i <= 2 && i <= n; i++) {
          j = i + int(rand() * (n - i + 1))
          if (j > n) j = n
          tmp = lines[i]; lines[i] = lines[j]; lines[j] = tmp
          print lines[i]
        }
      }'
}

# ---------------------------------------------------------------------------
# Prompt rendering
# ---------------------------------------------------------------------------

_pdr_render_refine_section() {
  # Emit the "## Refine From Prior Attempts" section using two slugs.
  local state_root="$1" task_id="$2" slug_a="$3" slug_b="$4"
  echo "## Refine From Prior Attempts"
  for slug in "$slug_a" "$slug_b"; do
    [ -n "$slug" ] || continue
    echo ""
    echo "### Prior Attempt: $slug"
    cat "${state_root}/${task_id}/pdr-rtv/rollouts/${slug}/summary.md"
  done
}

_pdr_render_spawn_prompt() {
  # Args: <iter> <state_root> <task_id> <candidate_slug>
  local iter="$1" state_root="$2" task_id="$3" cand="$4"
  echo "TaskId: $task_id"
  echo "Iteration: $iter"
  echo "Candidate: $cand"
  echo ""
  if [ "$iter" -ge 1 ]; then
    local pair
    pair="$(_pdr_sample_two_prior_summaries "$state_root" "$task_id" "$cand")"
    local slug_a slug_b
    slug_a="$(echo "$pair" | sed -n '1p')"
    slug_b="$(echo "$pair" | sed -n '2p')"
    _pdr_render_refine_section "$state_root" "$task_id" "$slug_a" "$slug_b"
  fi
}

# ---------------------------------------------------------------------------
# Test seam: log spawn prompts + worktree events to env-configured files
# ---------------------------------------------------------------------------

_pdr_record_spawn() {
  # Args: <iter> <candidate_slug> <prompt_text>
  local iter="$1" cand="$2" prompt="$3"
  local prompt_log="${PDR_RTV_TEST_PROMPT_LOG:-}"
  if [ -n "$prompt_log" ]; then
    local prompt_dir prompt_file
    prompt_dir="$(dirname "$prompt_log")"
    prompt_file="${prompt_dir}/prompt-iter${iter}-${cand}.txt"
    printf '%s\n' "$prompt" > "$prompt_file"
    printf 'CANDIDATE: %s ITER: %s FILE: %s\n' "$cand" "$iter" "$prompt_file" \
      >> "$prompt_log"
  fi
}

_pdr_log_worktree_event() {
  # Args: <event-type: WORKTREE_OPEN|WORKTREE_CLOSE> <iter> <candidate_slug>
  local event="$1" iter="$2" cand="$3"
  local wt_log="${PDR_RTV_TEST_WORKTREE_LOG:-}"
  [ -n "$wt_log" ] || return 0
  printf '%s iter=%s slug=%s\n' "$event" "$iter" "$cand" >> "$wt_log"
}

# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

dispatch_iteration() {
  if [ "$#" -lt 1 ]; then
    echo "dispatch_iteration: usage: dispatch_iteration <iter> --task-id ID --state-root DIR --candidates a,b,..." >&2
    return 2
  fi
  local iter="$1"; shift
  case "$iter" in (0|1|2) ;; (*) echo "dispatch_iteration: iter must be 0..2 (got: $iter)" >&2; return 2 ;; esac
  _pdr_parse_kv_args "$@" || return $?

  local IFS=','
  # shellcheck disable=SC2206
  local cands=( $_PDR_CANDIDATES )
  unset IFS

  local cand prompt
  for cand in "${cands[@]}"; do
    _pdr_log_worktree_event WORKTREE_OPEN "$iter" "$cand"
    prompt="$(_pdr_render_spawn_prompt "$iter" "$_PDR_STATE_ROOT" "$_PDR_TASK_ID" "$cand")"
    _pdr_record_spawn "$iter" "$cand" "$prompt"
  done

  # Iteration-1 must reap its OWN worktrees in-line, since reap_iteration_0_*
  # only handles iter-0. Iter-0 worktrees stay OPEN until reap is called
  # explicitly (per AC3-bis serialisation contract).
  if [ "$iter" -ge 1 ]; then
    for cand in "${cands[@]}"; do
      _pdr_log_worktree_event WORKTREE_CLOSE "$iter" "$cand"
    done
  fi
}

reap_iteration_0_worktrees() {
  _pdr_parse_iter0_reap_args "$@" || return $?
  # Reap every iter-0 candidate whose summary.md has been persisted.
  local slug
  while IFS= read -r slug; do
    [ -n "$slug" ] || continue
    _pdr_log_worktree_event WORKTREE_CLOSE 0 "$slug"
  done < <(_pdr_list_prior_summary_slugs "$_PDR_STATE_ROOT" "$_PDR_TASK_ID")
}

_pdr_parse_iter0_reap_args() {
  _PDR_TASK_ID=""
  _PDR_STATE_ROOT=""
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --task-id)    _PDR_TASK_ID="$2";    shift 2 ;;
      --state-root) _PDR_STATE_ROOT="$2"; shift 2 ;;
      *) echo "reap_iteration_0_worktrees: unknown flag: $1" >&2; return 2 ;;
    esac
  done
  [ -n "$_PDR_TASK_ID" ]    || { echo "reap_iteration_0_worktrees: --task-id required" >&2; return 2; }
  [ -n "$_PDR_STATE_ROOT" ] || { echo "reap_iteration_0_worktrees: --state-root required" >&2; return 2; }
}

export -f dispatch_iteration reap_iteration_0_worktrees \
          _pdr_parse_kv_args _pdr_parse_iter0_reap_args \
          _pdr_list_prior_summary_slugs _pdr_seed_int \
          _pdr_sample_two_prior_summaries \
          _pdr_render_refine_section _pdr_render_spawn_prompt \
          _pdr_record_spawn _pdr_log_worktree_event
