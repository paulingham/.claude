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

_qg_check_freshness() {
  local task="${CLAUDE_PIPELINE_TASK_ID:-unknown}" path head verdict
  path="pipeline-state/$task/verification-evidence.json"
  [[ -f "$path" ]] || { echo "[qg] freshness: FAIL (no evidence)" >&2; return 1; }
  head=$(jq -r '.git_head' "$path" 2>/dev/null); verdict=$(jq -r '.verdict' "$path" 2>/dev/null)
  [[ "$head" == "$(git rev-parse HEAD 2>/dev/null)" && "$verdict" =~ ^VERIFIED ]] && { echo "[qg] freshness: PASS" >&2; return 0; }; echo "[qg] freshness: FAIL" >&2; return 1
}
