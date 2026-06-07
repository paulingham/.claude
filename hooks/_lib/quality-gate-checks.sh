#!/usr/bin/env bash
# Per-check functions for quality-gate.sh (extracted for SubagentStop reuse).
# NO set -e. Functions return 0 (pass) / 1 (fail). Never call exit directly.
# Two-level dispatch: top-level dispatchers → per-runtime leaves. Each ≤8 lines.

_qg_detect_runtime() {
  [[ -f package.json ]] && { echo node; return; }
  [[ -f Gemfile ]] && { echo ruby; return; }
  ([[ -f pyproject.toml ]] || [[ -f requirements.txt ]]) && { echo python; return; }
  echo unknown
}

# Skip-eligible (return 0) ONLY when the HEAD~1..HEAD diff was computed AND has
# zero files matching $1. Returns 1 when the diff touches $1 OR is undeterminable
# (no/failed diff) — conservative: run the suite on uncertainty.
_qg_diff_skip_eligible() {
  local pat="$1" files
  files=$(git diff --name-only HEAD~1 HEAD 2>/dev/null) || return 1
  [[ -z "$files" ]] && return 1
  printf '%s\n' "$files" | grep -qE "$pat" && return 1
  return 0
}

_qg_check_tests() {
  local rt=${1:-$(_qg_detect_runtime)}
  case "$rt" in ruby) _qg_check_tests_ruby ;; node) _qg_check_tests_node ;; python) _qg_check_tests_python ;; *) return 0 ;; esac
}
_qg_check_tests_ruby() { _qg_diff_skip_eligible '\.rb$' && { echo "[qg] tests: PASS (no Ruby files changed)" >&2; return 0; }; command -v bundle &>/dev/null || return 0; bundle exec rspec --format progress &>/dev/null && { echo "[qg] tests: PASS" >&2; return 0; }; echo "[qg] tests: FAIL" >&2; return 1; }
_qg_check_tests_node() { _qg_diff_skip_eligible '\.(ts|tsx|js|jsx|mjs|cjs)$' && { echo "[qg] tests: PASS (no JS/TS files changed)" >&2; return 0; }; command -v npm &>/dev/null || return 0; npm test &>/dev/null && { echo "[qg] tests: PASS" >&2; return 0; }; echo "[qg] tests: FAIL" >&2; return 1; }
# Baseline path for tolerated pre-existing pytest failures (env-local runtime state).
_qg_known_red_path() { printf '%s/pipeline-state/quality-gate/known-red.txt' "${HARNESS_DATA:-$HOME/.claude}"; }

# Run pytest once, emit currently-failing node IDs (one per line, sorted/unique) on stdout.
# `-rfE` surfaces both FAILED and (collection) ERROR summary lines; the
# --continue flag prevents collection errors (e.g. an unprovisioned optional dep)
# from aborting the whole run and silently hiding the real red set. rc captured via
# `|| true` so the caller's pipefail cannot kill the function on a red suite.
_qg_pytest_failures() {
  local out; out=$(pytest -q --no-header -p no:cacheprovider -o addopts="" -rfE --continue-on-collection-errors 2>/dev/null || true)
  printf '%s\n' "$out" | grep -oE '^(FAILED|ERROR|SUBFAILED[^ ]*) +tests/[^ ]+' \
    | grep -oE 'tests/[^ ]+' | sort -u
}

# Concatenate N consecutive full pytest runs' failure sets (newline-joined, with
# duplicates preserved so counts are meaningful). This suite is NONDETERMINISTIC in
# full-run mode (~20 node IDs flap run-to-run from inter-test state pollution); a single
# run's red set is unstable. CLAUDE_QG_TEST_RUNS overrides the run count (default 2).
_qg_pytest_runs() {
  local runs="${CLAUDE_QG_TEST_RUNS:-2}" merged="" i
  for ((i = 0; i < runs; i++)); do merged=$(printf '%s\n%s\n' "$merged" "$(_qg_pytest_failures)"); done
  printf '%s\n' "$merged" | grep -v '^$'
}

# Confirmed (stable) failures = intersection of all runs: node IDs that failed in EVERY
# run. Flap collapses here — a flappy test rarely fails all N runs, a real one always does.
_qg_pytest_confirmed() {
  local runs="${CLAUDE_QG_TEST_RUNS:-2}"
  printf '%s\n' "$1" | sort | uniq -c | awk -v n="$runs" '$1 == n {print $2}'
}

# Count of flappy (non-confirmed) node IDs: union minus intersection across the runs.
_qg_pytest_flappy_count() {
  local union confirmed
  union=$(printf '%s\n' "$1" | sort -u | grep -c .)
  confirmed=$(_qg_pytest_confirmed "$1" | grep -c .)
  printf '%s' "$((union - confirmed))"
}

# Read baseline node IDs, ignoring blank lines and #-comment/provenance lines.
_qg_read_baseline() { grep -vE '^[[:space:]]*(#|$)' "$1" 2>/dev/null | sort -u; }

_qg_check_tests_python() {
  _qg_diff_skip_eligible '\.py$' && { echo "[qg] tests: PASS (no Python files changed)" >&2; return 0; }
  command -v pytest &>/dev/null || return 0
  local baseline merged confirmed flappy
  baseline=$(_qg_known_red_path); merged=$(_qg_pytest_runs)
  confirmed=$(_qg_pytest_confirmed "$merged"); flappy=$(_qg_pytest_flappy_count "$merged")
  [[ -f "$baseline" ]] || { _qg_tests_python_no_baseline "$confirmed" "$flappy"; return $?; }
  local new_red; new_red=$(comm -23 <(printf '%s\n' "$confirmed" | grep -v '^$') <(_qg_read_baseline "$baseline"))
  _qg_tests_python_verdict "$new_red" "$(_qg_read_baseline "$baseline" | grep -c .)" "$flappy"
}

# First-run fallback: no baseline recorded → strict (any CONFIRMED failure fails), with hint.
_qg_tests_python_no_baseline() {
  [[ -z "${1//[[:space:]]/}" ]] && { echo "[qg] tests: PASS (${2:-0} flappy ignored)" >&2; return 0; }
  echo "[qg] tests: FAIL (no known-red baseline; run scripts/qg-baseline-record.sh to record current red as baseline)" >&2
  return 1
}

# Verdict on the new-red set: empty → tolerate pre-existing; else list NEW RED and fail.
_qg_tests_python_verdict() {
  local new_red="$1" base_count="$2" flappy="${3:-0}"
  [[ -z "${new_red//[[:space:]]/}" ]] && { echo "[qg] tests: PASS ($base_count pre-existing red tolerated, $flappy flappy ignored)" >&2; return 0; }
  printf '%s\n' "$new_red" | grep -v '^$' | sed 's/^/[qg]   NEW RED: /' >&2
  echo "[qg] tests: FAIL ($(printf '%s\n' "$new_red" | grep -c .) new regressions confirmed in both runs)" >&2
  return 1
}

_qg_check_lint() {
  local rt=${1:-$(_qg_detect_runtime)}
  case "$rt" in ruby) _qg_check_lint_ruby ;; node) _qg_check_lint_node ;; python) _qg_check_lint_python ;; *) return 0 ;; esac
}
_qg_check_lint_ruby() { command -v bundle &>/dev/null || return 0; bundle exec rubocop --version &>/dev/null 2>&1 || return 0; bundle exec rubocop --format simple --fail-level E &>/dev/null && { echo "[qg] lint: PASS" >&2; return 0; }; echo "[qg] lint: FAIL" >&2; return 1; }
_qg_check_lint_node() { npx eslint --version &>/dev/null 2>&1 || return 0; npx eslint . --max-warnings 0 &>/dev/null && { echo "[qg] lint: PASS" >&2; return 0; }; echo "[qg] lint: FAIL" >&2; return 1; }
_qg_check_lint_python() { command -v ruff &>/dev/null || return 0; ruff check . &>/dev/null && { echo "[qg] lint: PASS" >&2; return 0; }; echo "[qg] lint: FAIL" >&2; return 1; }

_qg_check_audit() {
  local rt=${1:-$(_qg_detect_runtime)}
  case "$rt" in ruby) _qg_check_audit_ruby ;; node) _qg_check_audit_node ;; python) _qg_check_audit_python ;; *) return 0 ;; esac
}
_qg_check_audit_ruby() { [[ -f Gemfile.lock ]] || return 0; command -v bundle &>/dev/null || return 0; bundle exec bundler-audit --version &>/dev/null 2>&1 || return 0; bundle exec bundler-audit check &>/dev/null && { echo "[qg] audit: PASS" >&2; return 0; }; echo "[qg] audit: FAIL" >&2; return 1; }
_qg_check_audit_node() { [[ -f package-lock.json ]] || return 0; npm audit --audit-level=high &>/dev/null && { echo "[qg] audit: PASS" >&2; return 0; }; echo "[qg] audit: FAIL" >&2; return 1; }
_qg_check_audit_python() { [[ -f requirements.txt ]] || return 0; command -v pip-audit &>/dev/null || return 0; pip-audit &>/dev/null && { echo "[qg] audit: PASS" >&2; return 0; }; echo "[qg] audit: FAIL" >&2; return 1; }

_qg_check_shape() {
  local changed; changed=$(git diff --name-only HEAD~1 HEAD 2>/dev/null | grep -E '\.(ts|tsx|js|jsx)$' | grep -vE '\.(test|spec)\.' | grep -vE '\.(config|babel|jest|eslint|prettier|tailwind)\.' || true)
  [[ -z "$changed" ]] && { echo "[qg] shape: PASS (no JS/TS files)" >&2; return 0; }
  local fail=0
  while IFS= read -r f; do [[ -f "$f" ]] || continue; [[ $(wc -l < "$f") -le 50 ]] || { echo "[qg] shape: FAIL ($f too long)" >&2; fail=1; }; done <<< "$changed"
  [[ $fail -eq 0 ]] && echo "[qg] shape: PASS" >&2
  return $fail
}

_qg_check_contract() {
  local dir
  for dir in spec/contracts test/contracts tests/contracts; do [[ -d "$dir" ]] && break || dir=""; done
  [[ -z "$dir" ]] && return 0
  local rt; rt=$(_qg_detect_runtime)
  case "$rt" in ruby) bundle exec rspec "$dir" &>/dev/null ;; node) npx jest "$dir" &>/dev/null ;; python) pytest "$dir" &>/dev/null ;; *) return 0 ;; esac \
    && { echo "[qg] contract: PASS" >&2; return 0; } || { echo "[qg] contract: FAIL" >&2; return 1; }
}

_qg_resolve_intake_path() {
  local task="$1" ws="${CLAUDE_WORKSTREAM:-}" candidate
  # HARNESS_DATA probes first (post-migration writes land here)
  if [[ -n "${HARNESS_DATA:-}" ]]; then
    if [[ -n "$ws" ]]; then
      candidate="${HARNESS_DATA}/pipeline-state/workstreams/$ws/$task/intake.md"
      [[ -f "$candidate" ]] && { printf '%s\n' "$candidate"; return; }
    fi
    candidate="${HARNESS_DATA}/pipeline-state/$task/intake.md"
    [[ -f "$candidate" ]] && { printf '%s\n' "$candidate"; return; }
  fi
  # Bare-path fallback (soak: legacy worktree-relative location)
  if [[ -n "$ws" ]]; then
    candidate="pipeline-state/workstreams/$ws/$task/intake.md"
    [[ -f "$candidate" ]] && { printf '%s\n' "$candidate"; return; }
  fi
  printf 'pipeline-state/%s/intake.md\n' "$task"
}

_qg_extract_intake_tier() {
  # Reads `tier_emitted: Tn` (preferred) or `tier: Tn` (short form) from
  # intake.md frontmatter. Tolerates whitespace and quoted values. Anchored
  # to line-start so `tier_initial:` cannot match.
  local intake="$1"
  [[ -f "$intake" ]] || return 0
  sed -n -E 's/^[[:space:]]*tier_emitted:[[:space:]]*"?(T[0-6])"?[[:space:]]*$/\1/p; s/^[[:space:]]*tier:[[:space:]]*"?(T[0-6])"?[[:space:]]*$/\1/p' \
    "$intake" | head -n 1
}

# Resolve root checkout from a named worktree via --git-common-dir.
# Returns absolute root path, or empty if resolution fails.
_qg_worktree_root() {
  local wt="$1" common_dir root_dir
  common_dir=$(git -C "$wt" rev-parse --git-common-dir 2>/dev/null) || return 0
  [[ -n "$common_dir" ]] || return 0
  root_dir=$(cd "$wt" && cd "$common_dir" && dirname "$(pwd -P)" 2>/dev/null) || return 0
  printf '%s' "$root_dir"
}

# Find evidence path using 6-priority search (worktree-local first, root fallback, HARNESS_DATA).
# Prints the path if found; returns 1 if nothing found.
# Waiver: ≤8-line limit exceeded; plan-authorized for the 6-priority search (P5/P6 added slice-b).
# HIGH-A: HARNESS_DATA guard uses [[ -n "${HARNESS_DATA:-}" ]] — silent skip when unset.
# HEAD-binding invariant (M4) unchanged: caller applies same jq .git_head check for all priorities.
_qg_find_evidence_path() {
  local wt="$1" task="$2" root_dir p
  # Priority 1: exact task-id, worktree-local
  [[ -n "$task" && -f "${wt}/pipeline-state/${task}/verification-evidence.json" ]] \
    && { printf '%s' "${wt}/pipeline-state/${task}/verification-evidence.json"; return 0; }
  # Priority 2: glob newest, worktree-local
  p=$(ls -t "${wt}"/pipeline-state/*/verification-evidence.json 2>/dev/null | head -1)
  [[ -f "$p" ]] && { printf '%s' "$p"; return 0; }
  # Priority 3+4: root fallback (only when wt is a named registered worktree)
  root_dir=$(_qg_worktree_root "$wt")
  if [[ -n "$root_dir" && "$root_dir" != "$wt" ]]; then
    [[ -n "$task" && -f "${root_dir}/pipeline-state/${task}/verification-evidence.json" ]] \
      && { printf '%s' "${root_dir}/pipeline-state/${task}/verification-evidence.json"; return 0; }
    p=$(ls -t "${root_dir}"/pipeline-state/*/verification-evidence.json 2>/dev/null | head -1)
    [[ -f "$p" ]] && { printf '%s' "$p"; return 0; }
  fi
  # Priority 5: exact task-id, HARNESS_DATA location (post-migration writes land here)
  if [[ -n "${HARNESS_DATA:-}" && -n "$task" ]]; then
    [[ -f "${HARNESS_DATA}/pipeline-state/${task}/verification-evidence.json" ]] \
      && { printf '%s' "${HARNESS_DATA}/pipeline-state/${task}/verification-evidence.json"; return 0; }
    # Priority 6: glob newest, HARNESS_DATA location
    p=$(ls -t "${HARNESS_DATA}"/pipeline-state/*/verification-evidence.json 2>/dev/null | head -1)
    [[ -f "$p" ]] && { printf '%s' "$p"; return 0; }
  fi
  return 1
}

_qg_check_freshness() {
  [[ "${CLAUDE_DISABLE_FRESHNESS_QG:-0}" == "1" ]] && return 0
  local command="${1:-}" wt="" head verdict path intake tier task
  task="${CLAUDE_PIPELINE_TASK_ID:-}"
  # Extract worktree path from COMMAND cd-prefix (two-pass: quoted then unquoted).
  # grep -m1 finds the FIRST matching line regardless of position in a multiline
  # command string, then sed extracts from that single line only. This fixes the
  # prior sed-only approach where sed's ^ anchor matched line-starts but the full
  # pipeline still emitted all non-matching lines, making wt a multiline value
  # that failed the -d test (root cause of 2026-06-03 stub-at-root workaround).
  if [[ -n "$command" ]]; then
    wt=$(printf '%s' "$command" | grep -m1 -E '^\(?[[:space:]]*cd[[:space:]]+"' | sed -E 's/^\(?[[:space:]]*cd[[:space:]]+"([^"]+)".*/\1/')
    if [[ -z "$wt" || ! -d "$wt" ]]; then
      wt=$(printf '%s' "$command" | grep -m1 -E '^\(?[[:space:]]*cd[[:space:]]+[^[:space:]"]' | sed -E 's/^\(?[[:space:]]*cd[[:space:]]+([^[:space:]"]+)[[:space:]]*&&.*/\1/')
    fi
    [[ -d "$wt" ]] || wt=""
  fi
  # Tier short-circuit (T0/T1 docs-only).
  intake=$(_qg_resolve_intake_path "${task:-unknown}"); tier=$(_qg_extract_intake_tier "$intake")
  [[ "$tier" == "T0" || "$tier" == "T1" ]] && { echo "[freshness] PASS (tier=$tier; docs-only, /verify not applicable)" >&2; return 0; }
  # Locate evidence: worktree-local first, then root fallback (Defect 2 fix).
  if [[ -n "$wt" ]]; then
    path=$(_qg_find_evidence_path "$wt" "$task")
  else
    local base="."
    path=""
    if [[ -n "$task" && -f "${base}/pipeline-state/${task}/verification-evidence.json" ]]; then
      path="${base}/pipeline-state/${task}/verification-evidence.json"
    else
      path=$(ls -t "${base}"/pipeline-state/*/verification-evidence.json 2>/dev/null | head -1)
    fi
    # Inline HARNESS_DATA fallback (when no cd-prefix worktree extracted)
    # HIGH-A: guard with [[ -n "${HARNESS_DATA:-}" ]] — silent skip when unset.
    if [[ -z "$path" && -n "${HARNESS_DATA:-}" ]]; then
      if [[ -n "$task" && -f "${HARNESS_DATA}/pipeline-state/${task}/verification-evidence.json" ]]; then
        path="${HARNESS_DATA}/pipeline-state/${task}/verification-evidence.json"
      else
        path=$(ls -t "${HARNESS_DATA}"/pipeline-state/*/verification-evidence.json 2>/dev/null | head -1)
      fi
    fi
  fi
  [[ -f "$path" ]] || { echo "[freshness] no verification-evidence; run /verify" >&2; return 1; }
  head=$(jq -r '.git_head' "$path" 2>/dev/null); verdict=$(jq -r '.verdict' "$path" 2>/dev/null)
  # SEC-4: when both expected task and evidence task_id are present and differ, fail.
  local eid; eid=$(jq -r '.task_id // empty' "$path" 2>/dev/null)
  if [[ -n "$task" && -n "$eid" && "$task" != "$eid" ]]; then
    echo "[freshness] evidence task_id=$eid != expected=$task; re-verify" >&2; return 1
  fi
  # Resolve worktree HEAD: git -C <wt> if we have a worktree, else cwd.
  local wt_head
  if [[ -n "$wt" ]]; then
    wt_head=$(git -C "$wt" rev-parse HEAD 2>/dev/null)
  else
    wt_head=$(git rev-parse HEAD 2>/dev/null)
  fi
  # CR-4: emit meaningful message when worktree HEAD cannot be resolved.
  if [[ -z "$wt_head" ]]; then
    echo "[freshness] could not resolve worktree HEAD at ${wt:-.}" >&2; return 1
  fi
  # Defect 3 fix: on HEAD mismatch, check if git_head matches any registered worktree.
  # Fail-closed: git worktree list failure → "matches no registered worktree HEAD" path.
  # If this fires incorrectly, check concurrent worktrees at same SHA; set CLAUDE_DISABLE_FRESHNESS_QG=1 to unblock
  if [[ "$head" != "$wt_head" ]]; then
    local repo_root wt_list_output matched_wt
    repo_root=$(_qg_worktree_root "$wt")
    repo_root="${repo_root:-$(git -C "$wt" rev-parse --show-toplevel 2>/dev/null)}"
    wt_list_output=$(git -C "${repo_root:-.}" worktree list --porcelain 2>/dev/null)
    if [[ -z "$wt_list_output" ]]; then
      echo "[freshness] state=$head worktree=$wt_head; could not enumerate worktrees; treating HEAD mismatch as stale — re-verify" >&2
      return 1
    fi
    matched_wt=$(printf '%s\n' "$wt_list_output" \
      | awk -v sha="$head" '/^worktree /{wt=substr($0,10)} /^HEAD /{if ($2==sha) print wt}' \
      | head -1)
    if [[ -n "$matched_wt" ]]; then
      echo "[freshness] state=$head worktree=$wt_head; evidence git_head=$head matches worktree $matched_wt HEAD (not $wt); possible evidence substitution — re-verify from correct worktree" >&2
    else
      echo "[freshness] state=$head worktree=$wt_head; evidence git_head=$head matches no registered worktree HEAD; evidence may be stub-edited — re-verify" >&2
    fi
    return 1
  fi
  [[ "$verdict" =~ ^VERIFIED ]] || { echo "[freshness] verdict=$verdict; re-verify" >&2; return 1; }
  echo "[freshness] PASS" >&2; return 0
}
