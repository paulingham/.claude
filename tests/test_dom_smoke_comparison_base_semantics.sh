#!/usr/bin/env bash
# AC14 — Comparison-base semantics: build a worktree 2 commits ahead of main,
# assert the documented diff command
#   git diff --name-only $(git merge-base HEAD main)...HEAD
# returns BOTH commits' files. Proves merge-base...HEAD semantics — bare
# `git diff --name-only HEAD~1...HEAD` would return only the latest commit's
# files and fail this test.
#
# Mock boundary: this test exercises the actual `git` command (no MCP, no
# Chrome). It builds a throwaway git repo to validate the diff semantics
# documented in Step 2d.
set -uo pipefail

PASS=0; FAIL=0

assert() {
  local label=$1; shift
  if "$@"; then echo "  ok: $label"; PASS=$((PASS + 1))
  else echo "  FAIL: $label"; FAIL=$((FAIL + 1)); fi
}

echo "Test step_2d_only_diffs_against_merge_base_main"

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

cd "$TMP"
git init -q -b main
git config user.email "test@test"
git config user.name "test"

# Seed main with a baseline file.
echo seed > seed.txt
git add seed.txt
git commit -q -m "seed"

# Branch off main, add 2 commits each touching a distinct file.
git switch -q -c feature
echo a > app/page.tsx.placeholder 2>/dev/null || { mkdir -p app && echo a > app/page.tsx; }
git add -A
git commit -q -m "commit 1: app/page.tsx"

mkdir -p src/components
echo b > src/components/Button.tsx
git add -A
git commit -q -m "commit 2: src/components/Button.tsx"

# Run the documented Step 2d diff command.
CHANGED=$(git diff --name-only $(git merge-base HEAD main)...HEAD)

# Both commits' files MUST appear.
if printf '%s\n' "$CHANGED" | grep -qx 'app/page.tsx'; then
  echo "  ok: changed-files contains app/page.tsx (commit 1)"; PASS=$((PASS + 1))
else
  echo "  FAIL: changed-files missing app/page.tsx — merge-base semantics broken"
  echo "  changed list:"; printf '    %s\n' "$CHANGED"
  FAIL=$((FAIL + 1))
fi

if printf '%s\n' "$CHANGED" | grep -qx 'src/components/Button.tsx'; then
  echo "  ok: changed-files contains src/components/Button.tsx (commit 2)"; PASS=$((PASS + 1))
else
  echo "  FAIL: changed-files missing src/components/Button.tsx"
  FAIL=$((FAIL + 1))
fi

# Sanity: bare `git diff --name-only HEAD~1...HEAD` returns only the latest
# commit's files — demonstrates why merge-base is required.
BARE=$(git diff --name-only HEAD~1...HEAD)
if printf '%s\n' "$BARE" | grep -qx 'app/page.tsx'; then
  echo "  FAIL: bare HEAD~1...HEAD unexpectedly includes commit 1 — control invalid"
  FAIL=$((FAIL + 1))
else
  echo "  ok: bare HEAD~1...HEAD correctly omits commit 1 (control)"; PASS=$((PASS + 1))
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1
