#!/usr/bin/env bash
# tdd-guard-pr.sh — helper for hooks/tdd-guard.sh.
# Diffs the PR base against HEAD, classifies each changed file
# (exempt | test | source), and blocks when source files exist
# in the diff but no matching test files do. Honors GITHUB_BASE_REF
# override; defaults to "main".

# Classify a single file: prints "exempt", "test", "source", or "skip".
_tdd_guard_classify() {
  local file="$1"
  case "$file" in
    *spec/*|*test/*|*tests/*|*__tests__/*|*.test.*|*.spec.*|*_test.go|*_test.py|*/test_*.py)
      echo "test"; return ;;
  esac
  case "$file" in
    *.md|*.json|*.yaml|*.yml|*.toml|*.lock|*.sh|*Gemfile|*package.json)
      echo "exempt"; return ;;
  esac
  case "$file" in
    *.rb|*.js|*.ts|*.jsx|*.tsx|*.py|*.go|*.java|*.cs|*.swift|*.kt)
      echo "source"; return ;;
  esac
  echo "skip"
}

# Iterate diff lines, count source vs test files. Args: $1 = diff text.
_tdd_guard_count() {
  local diff_text="$1" file kind src=0 tst=0
  while IFS= read -r file; do
    [[ -z "$file" ]] && continue
    kind=$(_tdd_guard_classify "$file")
    [[ "$kind" == "source" ]] && src=$((src + 1))
    [[ "$kind" == "test"   ]] && tst=$((tst + 1))
  done <<< "$diff_text"
  echo "$src $tst"
}

# Top-level: parse args, run diff, decide block vs allow. Returns 0 on
# allow, 1 on block. Caller (tdd-guard.sh) is responsible for exit so the
# allow path can emit a `passed` event before exiting.
_tdd_guard_pr_run() {
  local cmd="$1" base="${GITHUB_BASE_REF:-main}" diff_text counts src tst
  diff_text="${TDD_GUARD_DIFF_FIXTURE:-$(git diff --name-only "${base}...HEAD" 2>/dev/null || true)}"
  [[ -z "$diff_text" ]] && return 0
  counts=$(_tdd_guard_count "$diff_text")
  src="${counts% *}"
  tst="${counts##* }"
  if [[ "$src" -gt 0 && "$tst" -eq 0 ]]; then
    jq -n --arg cmd "$cmd" --arg base "$base" \
      '{"decision":"block","reason":("TDD Guard: PR diff against base \u0027" + $base + "\u0027 contains source changes with no test changes. Add the failing test stubs from the architect plan to the diff, or split the change.")}'
    return 1
  fi
  return 0
}
