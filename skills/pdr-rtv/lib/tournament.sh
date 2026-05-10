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
  # Args: <slug_a> <slug_b> [<round_idx>] [<match_idx>]
  # Test-seamed verdict picker. Production behaviour (AC7): when both
  # CLAUDE_PDR_RTV_LIVE_PICKER=1 and PDR_RTV_VERDICT_DIR are exported,
  # read `${PDR_RTV_VERDICT_DIR}/<round>-<idx>.verdict` (1-based round,
  # 0-based match — matches `_pdr_tournament_md_append_match` indexing)
  # and parse the FIRST LINE for `WINNER: A` or `WINNER: B`. Trailing
  # rationale lines are tolerated. On parse success the chosen slug is
  # returned and diff-stat is NOT consulted.
  #
  # On verdict-file missing OR malformed (no first-line WINNER:A|B),
  # fall back to `_pdr_pick_winner_by_diff_stat` AND record a parse-
  # failure event in the sentinel directory so `run_tournament` can
  # append a `## Re-routes` line after the bracket walk completes.
  #
  # Placeholder-detection (F3): when neither the test override nor the
  # CLAUDE_PDR_RTV_LIVE_PICKER opt-in is set, the diff-stat heuristic acts
  # as the primary verdict source. That is a gate-bypass surface — touch
  # a sentinel file so `run_tournament` can append the F3 re-route line.
  # The bracket walks inside a process-substitution subshell, so global
  # vars would not propagate; the filesystem sentinel survives the
  # subshell boundary.
  local slug_a="$1" slug_b="$2"
  local round_idx="${3:-}" match_idx="${4:-}"
  case "${PDR_RTV_TEST_VERDICT_OVERRIDE:-}" in
    alpha-first)
      [ "$slug_a" \< "$slug_b" ] && printf '%s' "$slug_a" || printf '%s' "$slug_b"
      return 0
      ;;
  esac
  if _pdr_live_picker_enabled; then
    local picked
    if picked="$(_pdr_pick_winner_from_verdict_file \
                   "$slug_a" "$slug_b" "$round_idx" "$match_idx")"; then
      printf '%s' "$picked"
      return 0
    fi
    # parse-failure path — fall through to diff-stat fallback below.
    _pdr_record_parse_failure "$round_idx" "$match_idx"
  elif [ -z "${CLAUDE_PDR_RTV_LIVE_PICKER:-}" ]; then
    # F3 placeholder sentinel — only when LIVE_PICKER is unset. When
    # LIVE_PICKER is set but VERDICT_DIR is missing (operator error or
    # legacy test seam), we skip the F3 reroute to keep AC2's positive
    # guarantee: the live-picker opt-in suppresses the placeholder
    # signal even when diff-stat is the actual tie-breaker path.
    if [ -n "${_PDR_T_PLACEHOLDER_SENTINEL:-}" ]; then
      : > "$_PDR_T_PLACEHOLDER_SENTINEL"
    fi
  fi
  _pdr_pick_winner_by_diff_stat "$slug_a" "$slug_b"
}

# AC7 — true when the orchestrator has wired the live picker (both env
# vars exported). False otherwise (fall through to legacy diff-stat).
_pdr_live_picker_enabled() {
  [ -n "${CLAUDE_PDR_RTV_LIVE_PICKER:-}" ] && [ -n "${PDR_RTV_VERDICT_DIR:-}" ]
}

# AC7 — read verdict file and emit chosen slug on stdout. Returns 0 on
# parse success, 1 on missing/malformed verdict (caller falls through to
# diff-stat). Parses FIRST LINE only — trailing rationale lines tolerated
# per `agents/patch-critic.md` § Tournament Mode output spec.
_pdr_pick_winner_from_verdict_file() {
  local slug_a="$1" slug_b="$2" round_idx="$3" match_idx="$4"
  [ -n "$round_idx" ] && [ -n "$match_idx" ] || return 1
  local verdict_file="${PDR_RTV_VERDICT_DIR}/${round_idx}-${match_idx}.verdict"
  [ -f "$verdict_file" ] || return 1
  local first_line
  first_line="$(head -n 1 "$verdict_file")"
  case "$first_line" in
    "WINNER: A") printf '%s' "$slug_a"; return 0 ;;
    "WINNER: B") printf '%s' "$slug_b"; return 0 ;;
    *)           return 1 ;;
  esac
}

# AC7 — record a parse-failure event so `run_tournament` can emit a
# `## Re-routes` line after the bracket walk completes. One file per
# match keeps the event reportable in deterministic order.
_pdr_record_parse_failure() {
  local round_idx="$1" match_idx="$2"
  [ -n "${_PDR_T_PARSE_FAILURE_DIR:-}" ] || return 0
  [ -n "$round_idx" ] && [ -n "$match_idx" ] || return 0
  : > "${_PDR_T_PARSE_FAILURE_DIR}/${round_idx}-${match_idx}"
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
  # AC3 — when meta is missing or carries an empty sha, write the
  # literal `sha: <unknown>` AND call the new sibling reroute helper to
  # append `meta-missing for <slug>`. The existing F3 zero-arg helper
  # `_pdr_tournament_md_append_reroute` is left untouched for callers
  # that need its placeholder-active line (a different surface).
  local slug="$1"
  local out_path sha
  out_path="$(_pdr_tournament_md_path)"
  sha="$(_pdr_rollout_meta_field "$slug" sha)"
  if [ -z "$sha" ]; then
    {
      echo "## Winner"
      echo "slug: ${slug}"
      echo "sha: <unknown>"
    } >> "$out_path"
    _pdr_tournament_md_append_meta_missing_reroute "$slug"
    return 0
  fi
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

# AC3 — sibling helper. Appends a `meta-missing for <slug>` line under
# the shared `## Re-routes` header. When the header is already present
# (e.g., AC2-bis or F3 emitted earlier), reuse it; otherwise add it.
_pdr_tournament_md_append_meta_missing_reroute() {
  local slug="$1"
  local out_path
  out_path="$(_pdr_tournament_md_path)"
  if ! grep -Fxq "## Re-routes" "$out_path" 2>/dev/null; then
    {
      echo ""
      echo "## Re-routes"
    } >> "$out_path"
  fi
  echo "meta-missing for ${slug}" >> "$out_path"
}

# AC7 — sibling helper. Appends a `parse-failure for match <round>.<idx>,
# fell back to diff-stat` line under the shared `## Re-routes` header
# for every match where the verdict file was malformed.
_pdr_tournament_md_append_parse_failure_reroute() {
  local round_idx="$1" match_idx="$2"
  local out_path
  out_path="$(_pdr_tournament_md_path)"
  if ! grep -Fxq "## Re-routes" "$out_path" 2>/dev/null; then
    {
      echo ""
      echo "## Re-routes"
    } >> "$out_path"
  fi
  echo "parse-failure for match ${round_idx}.${match_idx}, fell back to diff-stat" >> "$out_path"
}

# AC2-bis — appended at run_tournament entry when both LIVE_PICKER and
# TEST_VERDICT_OVERRIDE are unset. Cause-then-symptom convention: this
# line lands BEFORE the F3 `placeholder picker active` line under the
# shared `## Re-routes` header.
_pdr_tournament_md_append_live_picker_missing_reroute() {
  local out_path
  out_path="$(_pdr_tournament_md_path)"
  if ! grep -Fxq "## Re-routes" "$out_path" 2>/dev/null; then
    {
      echo ""
      echo "## Re-routes"
    } >> "$out_path"
  fi
  echo "live-picker-flag-missing — operator must export CLAUDE_PDR_RTV_LIVE_PICKER=1" >> "$out_path"
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
    winner="$(_pdr_pick_winner "$a" "$b" "$round_idx" "$match_idx")"
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

  # AC2-bis — positive-assertion check at entry. When both LIVE_PICKER
  # and TEST_VERDICT_OVERRIDE are unset (production without the flag),
  # surface the cause BEFORE the bracket walk so the reroute lands
  # BEFORE F3's symptom line under the shared `## Re-routes` header.
  if [ -z "${CLAUDE_PDR_RTV_LIVE_PICKER:-}" ] \
     && [ -z "${PDR_RTV_TEST_VERDICT_OVERRIDE:-}" ]; then
    echo "run_tournament: live-picker-flag-missing — operator must export CLAUDE_PDR_RTV_LIVE_PICKER=1" >&2
    _pdr_tournament_md_append_live_picker_missing_reroute
  fi

  # Placeholder-detection sentinel — survives subshell boundaries (the
  # round walk runs inside `< <(...)` process substitution, so a global
  # var would not propagate). Cleaned up at function exit.
  export _PDR_T_PLACEHOLDER_SENTINEL
  _PDR_T_PLACEHOLDER_SENTINEL="$(mktemp -t pdr-rtv-placeholder.XXXXXX)"
  rm -f "$_PDR_T_PLACEHOLDER_SENTINEL"

  # AC7 — parse-failure event dir. Picker writes one file per match
  # whose verdict file is missing/malformed; we replay them here as
  # `## Re-routes` lines after the bracket walk completes.
  export _PDR_T_PARSE_FAILURE_DIR
  _PDR_T_PARSE_FAILURE_DIR="$(mktemp -d -t pdr-rtv-parsefail.XXXXXX)"

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
  _pdr_tournament_replay_parse_failures
  rm -f "$_PDR_T_PLACEHOLDER_SENTINEL"
  rm -rf "$_PDR_T_PARSE_FAILURE_DIR"
  unset _PDR_T_PLACEHOLDER_SENTINEL _PDR_T_PARSE_FAILURE_DIR
}

# AC7 — replay parse-failure events as `## Re-routes` lines. Iterates
# the sentinel directory in lexical order (round-major, match-minor) so
# multiple failures within a tournament are reported deterministically.
_pdr_tournament_replay_parse_failures() {
  [ -d "${_PDR_T_PARSE_FAILURE_DIR:-}" ] || return 0
  local entry round_idx match_idx base
  for entry in "$_PDR_T_PARSE_FAILURE_DIR"/*; do
    [ -e "$entry" ] || continue
    base="$(basename "$entry")"
    round_idx="${base%%-*}"
    match_idx="${base#*-}"
    _pdr_tournament_md_append_parse_failure_reroute "$round_idx" "$match_idx"
  done
}

export -f run_tournament \
          _pdr_tournament_parse_args _pdr_tournament_validate_csv \
          _pdr_tournament_md_path \
          _pdr_rollout_meta_field _pdr_render_comparison_prompt \
          _pdr_record_comparison _pdr_record_winner \
          _pdr_pick_winner _pdr_pick_winner_by_diff_stat \
          _pdr_live_picker_enabled \
          _pdr_pick_winner_from_verdict_file \
          _pdr_record_parse_failure \
          _pdr_tournament_md_init _pdr_tournament_md_append_match \
          _pdr_tournament_md_append_winner \
          _pdr_tournament_md_append_reroute \
          _pdr_tournament_md_append_meta_missing_reroute \
          _pdr_tournament_md_append_parse_failure_reroute \
          _pdr_tournament_md_append_live_picker_missing_reroute \
          _pdr_tournament_replay_parse_failures \
          _pdr_run_round
