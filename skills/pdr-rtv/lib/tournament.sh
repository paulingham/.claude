#!/usr/bin/env bash
# tournament.sh — pdr-rtv single-elimination pairwise tournament over rollout summaries.
#
# Public function:
#   run_tournament --task-id ID --state-root DIR --candidates a,b,c,...
#       Runs single-elimination pairwise comparison over the candidate
#       slugs until one winner remains. Each comparison spawns
#       patch-critic in tournament mode (Mode: tournament + Candidates: A,B
#       prompt tokens). Bracket order is deterministic given CLAUDE_PDR_SEED.
#
# Outputs:
#   - pipeline-state/{task-id}/pdr-rtv/tournament.md (frontmatter, every match,
#     `## Winner` section).
#
# Test seam:
#   - PDR_RTV_TEST_TOURNAMENT_LOG: when set, every comparison emits a
#     `COMPARE iter=R slug_a=A slug_b=B file=<path>` line, and every match
#     winner emits a `WINNER iter=R slug=W` line. The comparison prompt is
#     written to `<dirname>/comparison-R-A-B.txt`.
#   - PDR_RTV_TEST_VERDICT_OVERRIDE: when set to "alpha-first", every
#     comparison picks the alphabetically-smaller slug. Production paths
#     leave this unset; the real implementation invokes patch-critic.
#
# Dependencies: distill.sh's summary directory layout is read here, so
# rollouts/<slug>/summary.md must already exist before run_tournament fires.

# Source the shared validator (path-traversal defense, F1).
_pdr_tournament_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
. "${_pdr_tournament_dir}/validate.sh"
unset _pdr_tournament_dir

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

_pdr_tournament_parse_args() {
  _PDR_T_TASK_ID=""
  _PDR_T_STATE_ROOT=""
  _PDR_T_CANDIDATES=""
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --task-id)     _PDR_T_TASK_ID="$2";    shift 2 ;;
      --state-root)  _PDR_T_STATE_ROOT="$2"; shift 2 ;;
      --candidates)  _PDR_T_CANDIDATES="$2"; shift 2 ;;
      *) echo "run_tournament: unknown flag: $1" >&2; return 2 ;;
    esac
  done
  [ -n "$_PDR_T_TASK_ID" ]    || { echo "run_tournament: --task-id required" >&2; return 2; }
  [ -n "$_PDR_T_STATE_ROOT" ] || { echo "run_tournament: --state-root required" >&2; return 2; }
  [ -n "$_PDR_T_CANDIDATES" ] || { echo "run_tournament: --candidates required" >&2; return 2; }
  _pdr_validate_task_id "$_PDR_T_TASK_ID" || return $?
  _pdr_tournament_validate_csv "$_PDR_T_CANDIDATES" || return $?
}

_pdr_tournament_validate_csv() {
  local csv="$1" slug
  local IFS=','
  # shellcheck disable=SC2206
  local items=( $csv )
  unset IFS
  for slug in "${items[@]}"; do
    _pdr_validate_slug "$slug" || return $?
  done
}

# ---------------------------------------------------------------------------
# Tournament state paths
# ---------------------------------------------------------------------------

_pdr_tournament_md_path() {
  printf '%s/%s/pdr-rtv/tournament.md' "$_PDR_T_STATE_ROOT" "$_PDR_T_TASK_ID"
}

_pdr_rollout_meta_field() {
  # Args: <slug> <field>
  # Reads `<state>/<task>/pdr-rtv/rollouts/<slug>/meta` and emits the
  # value for <field> (e.g. diff_stat, sha). Empty on missing.
  local slug="$1" field="$2"
  local meta_file="${_PDR_T_STATE_ROOT}/${_PDR_T_TASK_ID}/pdr-rtv/rollouts/${slug}/meta"
  [ -f "$meta_file" ] || { printf ''; return; }
  awk -v k="$field" -F= '$1 == k { print $2; exit }' "$meta_file"
}

# ---------------------------------------------------------------------------
# Comparison spawn (test-seamed)
# ---------------------------------------------------------------------------

_pdr_render_comparison_prompt() {
  # Args: <slug_a> <slug_b>
  local slug_a="$1" slug_b="$2"
  echo "subagent_type: patch-critic"
  echo "Mode: tournament"
  echo "Candidates: ${slug_a},${slug_b}"
  echo ""
  echo "## Summary A: ${slug_a}"
  cat "${_PDR_T_STATE_ROOT}/${_PDR_T_TASK_ID}/pdr-rtv/rollouts/${slug_a}/summary.md"
  echo ""
  echo "## Summary B: ${slug_b}"
  cat "${_PDR_T_STATE_ROOT}/${_PDR_T_TASK_ID}/pdr-rtv/rollouts/${slug_b}/summary.md"
}

_pdr_record_comparison() {
  # Args: <round_idx> <slug_a> <slug_b> <prompt_text>
  # Writes the prompt to a per-comparison file and logs to the test seam.
  local round_idx="$1" slug_a="$2" slug_b="$3" prompt="$4"
  local log="${PDR_RTV_TEST_TOURNAMENT_LOG:-}"
  [ -n "$log" ] || return 0
  local log_dir prompt_file
  log_dir="$(dirname "$log")"
  prompt_file="${log_dir}/comparison-${round_idx}-${slug_a}-${slug_b}.txt"
  printf '%s\n' "$prompt" > "$prompt_file"
  printf 'COMPARE iter=%s slug_a=%s slug_b=%s file=%s\n' \
    "$round_idx" "$slug_a" "$slug_b" "$prompt_file" >> "$log"
}

_pdr_record_winner() {
  # Args: <round_idx> <slug>
  local round_idx="$1" slug="$2"
  local log="${PDR_RTV_TEST_TOURNAMENT_LOG:-}"
  [ -n "$log" ] || return 0
  printf 'WINNER iter=%s slug=%s\n' "$round_idx" "$slug" >> "$log"
}

_pdr_pick_winner() {
  # Args: <slug_a> <slug_b>
  # Test-seamed verdict picker. Production: invokes patch-critic via Agent
  # tool (out-of-scope for Slice 2; orchestrator-side wiring lands in Slice 3).
  # Test path honours PDR_RTV_TEST_VERDICT_OVERRIDE.
  #
  # Placeholder-detection (F3): when neither the test override nor the
  # CLAUDE_PDR_RTV_LIVE_PICKER opt-in is set, the diff-stat heuristic acts
  # as the primary verdict source. That is a gate-bypass surface — touch a
  # sentinel file so `run_tournament` can append a `## Re-routes` section
  # AFTER the bracket walk completes. (The bracket walks inside a process-
  # substitution subshell, so a global var would not propagate; the
  # filesystem sentinel survives the subshell boundary.)
  local slug_a="$1" slug_b="$2"
  case "${PDR_RTV_TEST_VERDICT_OVERRIDE:-}" in
    alpha-first)
      [ "$slug_a" \< "$slug_b" ] && printf '%s' "$slug_a" || printf '%s' "$slug_b"
      ;;
    *)
      if [ -z "${CLAUDE_PDR_RTV_LIVE_PICKER:-}" ] && [ -n "${_PDR_T_PLACEHOLDER_SENTINEL:-}" ]; then
        : > "$_PDR_T_PLACEHOLDER_SENTINEL"
      fi
      _pdr_pick_winner_by_diff_stat "$slug_a" "$slug_b"
      ;;
  esac
}

_pdr_pick_winner_by_diff_stat() {
  local slug_a="$1" slug_b="$2"
  local diff_a diff_b
  diff_a="$(_pdr_rollout_meta_field "$slug_a" diff_stat)"
  diff_b="$(_pdr_rollout_meta_field "$slug_b" diff_stat)"
  diff_a="${diff_a:-0}"
  diff_b="${diff_b:-0}"
  if [ "$diff_a" -lt "$diff_b" ]; then
    printf '%s' "$slug_a"
  elif [ "$diff_b" -lt "$diff_a" ]; then
    printf '%s' "$slug_b"
  else
    [ "$slug_a" \< "$slug_b" ] && printf '%s' "$slug_a" || printf '%s' "$slug_b"
  fi
}

# ---------------------------------------------------------------------------
# Tournament markdown writer
# ---------------------------------------------------------------------------

_pdr_tournament_md_init() {
  local out_path
  out_path="$(_pdr_tournament_md_path)"
  mkdir -p "$(dirname "$out_path")"
  {
    echo "---"
    echo "task_id: ${_PDR_T_TASK_ID}"
    echo "phase: build"
    echo "mode: tournament"
    echo "---"
    echo ""
    echo "# Tournament Bracket"
    echo ""
  } > "$out_path"
}

_pdr_tournament_md_append_match() {
  # Args: <round_idx> <match_idx> <slug_a> <slug_b> <winner>
  local round_idx="$1" match_idx="$2" slug_a="$3" slug_b="$4" winner="$5"
  local out_path
  out_path="$(_pdr_tournament_md_path)"
  {
    echo "### Match ${round_idx}.${match_idx}"
    echo "- candidates: ${slug_a} vs ${slug_b}"
    echo "- winner: ${winner}"
    echo ""
  } >> "$out_path"
}

_pdr_tournament_md_append_winner() {
  # Args: <slug>
  local slug="$1"
  local out_path sha
  out_path="$(_pdr_tournament_md_path)"
  sha="$(_pdr_rollout_meta_field "$slug" sha)"
  {
    echo "## Winner"
    echo "slug: ${slug}"
    echo "sha: ${sha}"
  } >> "$out_path"
}

_pdr_tournament_md_append_reroute() {
  # F3 — appended when _pdr_pick_winner fell through to the diff-stat
  # heuristic without orchestrator-level patch-critic wiring. Reflect step
  # surfaces this as a WARNING; pipeline never silently ships a diff-stat-
  # only winner without the operator seeing it.
  local out_path
  out_path="$(_pdr_tournament_md_path)"
  {
    echo ""
    echo "## Re-routes"
    echo "placeholder picker active (diff-stat heuristic) — orchestrator-side patch-critic Agent dispatch pending"
  } >> "$out_path"
}

# ---------------------------------------------------------------------------
# Bracket walk (single-elimination)
# ---------------------------------------------------------------------------

_pdr_run_round() {
  # Args: <round_idx> <space-separated slug list>
  # Emits the per-match winners on stdout (one per line, used to drive the
  # next round). Side effects: records each comparison to the test-seam log
  # AND appends a match entry to tournament.md. Per-match WINNER records
  # are NOT emitted to the test log — only the FINAL tournament winner is
  # logged via _pdr_record_winner once the bracket collapses (see
  # run_tournament). This keeps the WINNER-line semantic aligned with
  # AC5's "exactly 1 winner emerges" assertion.
  local round_idx="$1"; shift
  local slugs=( "$@" )
  local i=0 match_idx=0 a b winner prompt
  while [ "$i" -lt "${#slugs[@]}" ]; do
    a="${slugs[$i]}"
    b="${slugs[$((i + 1))]:-}"
    if [ -z "$b" ]; then
      # Odd contestant — automatic bye.
      printf '%s\n' "$a"
      i=$((i + 1))
      continue
    fi
    prompt="$(_pdr_render_comparison_prompt "$a" "$b")"
    _pdr_record_comparison "$round_idx" "$a" "$b" "$prompt"
    winner="$(_pdr_pick_winner "$a" "$b")"
    _pdr_tournament_md_append_match "$round_idx" "$match_idx" "$a" "$b" "$winner"
    printf '%s\n' "$winner"
    i=$((i + 2))
    match_idx=$((match_idx + 1))
  done
}

# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

run_tournament() {
  _pdr_tournament_parse_args "$@" || return $?

  local IFS=','
  # shellcheck disable=SC2206
  local cands=( $_PDR_T_CANDIDATES )
  unset IFS

  _pdr_tournament_md_init
  # Placeholder-detection sentinel — survives subshell boundaries (the
  # round walk runs inside `< <(...)` process substitution, so a global
  # var would not propagate). Cleaned up at function exit.
  export _PDR_T_PLACEHOLDER_SENTINEL
  _PDR_T_PLACEHOLDER_SENTINEL="$(mktemp -t pdr-rtv-placeholder.XXXXXX)"
  rm -f "$_PDR_T_PLACEHOLDER_SENTINEL"

  local round_idx=1
  local current=( "${cands[@]}" )
  while [ "${#current[@]}" -gt 1 ]; do
    local next=()
    while IFS= read -r slug; do
      [ -n "$slug" ] && next+=( "$slug" )
    done < <(_pdr_run_round "$round_idx" "${current[@]}")
    current=( "${next[@]}" )
    round_idx=$((round_idx + 1))
  done

  local final_winner="${current[0]}"
  _pdr_record_winner "final" "$final_winner"
  _pdr_tournament_md_append_winner "$final_winner"
  if [ -e "$_PDR_T_PLACEHOLDER_SENTINEL" ]; then
    _pdr_tournament_md_append_reroute
  fi
  rm -f "$_PDR_T_PLACEHOLDER_SENTINEL"
  unset _PDR_T_PLACEHOLDER_SENTINEL
}

export -f run_tournament \
          _pdr_tournament_parse_args _pdr_tournament_validate_csv \
          _pdr_tournament_md_path \
          _pdr_rollout_meta_field _pdr_render_comparison_prompt \
          _pdr_record_comparison _pdr_record_winner \
          _pdr_pick_winner _pdr_pick_winner_by_diff_stat \
          _pdr_tournament_md_init _pdr_tournament_md_append_match \
          _pdr_tournament_md_append_winner \
          _pdr_tournament_md_append_reroute _pdr_run_round
