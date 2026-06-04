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

_qg_check_tests() {
  local rt=${1:-$(_qg_detect_runtime)}
  case "$rt" in ruby) _qg_check_tests_ruby ;; node) _qg_check_tests_node ;; python) _qg_check_tests_python ;; *) return 0 ;; esac
}
_qg_check_tests_ruby() { command -v bundle &>/dev/null || return 0; bundle exec rspec --format progress &>/dev/null && { echo "[qg] tests: PASS" >&2; return 0; }; echo "[qg] tests: FAIL" >&2; return 1; }
_qg_check_tests_node() { command -v npm &>/dev/null || return 0; npm test &>/dev/null && { echo "[qg] tests: PASS" >&2; return 0; }; echo "[qg] tests: FAIL" >&2; return 1; }
_qg_check_tests_python() { command -v pytest &>/dev/null || return 0; pytest --tb=no -q &>/dev/null && { echo "[qg] tests: PASS" >&2; return 0; }; echo "[qg] tests: FAIL" >&2; return 1; }

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
  # Locate evidence: task-id hint if set + present, else glob newest.
  local base="${wt:-.}"
  path=""
  if [[ -n "$task" && -f "${base}/pipeline-state/${task}/verification-evidence.json" ]]; then
    path="${base}/pipeline-state/${task}/verification-evidence.json"
  else
    path=$(ls -t "${base}"/pipeline-state/*/verification-evidence.json 2>/dev/null | head -1)
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
  [[ "$head" != "$wt_head" ]] && { echo "[freshness] state=$head worktree=$wt_head; HEAD moved since /verify" >&2; return 1; }
  [[ "$verdict" =~ ^VERIFIED ]] || { echo "[freshness] verdict=$verdict; re-verify" >&2; return 1; }
  echo "[freshness] PASS" >&2; return 0
}
