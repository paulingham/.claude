#!/usr/bin/env bash
# Slice C AC-C6 — same-commit-staging gate.
#
# If skills/cache-audit/SKILL.md is staged, protocols/verdict-catalog.md AND
# protocols/skill-directory.md MUST also be staged in the same commit.
# Prevents the bidirectional-invariant break window where a verdict-emitting
# skill ships without its catalog entry.
#
# Strategy: take a git-index snapshot (set of staged paths), assert the
# atomic invariant. Runs in a fixture worktree to avoid mutating real index.

set -uo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PASS=0; FAIL=0

echo "Test cache_audit_skill_and_verdict_row_atomic"

# Build a throwaway git repo with three staged path samples and run the
# invariant check against the staged set.
TMP=$(mktemp -d -t catomic.XXXXXX)
trap 'rm -rf "$TMP"' EXIT

cd "$TMP"
git init -q .
git config user.email "test@local"
git config user.name "test"

mkdir -p skills/cache-audit rules protocols

# CASE 1 — all three staged together: PASS.
touch skills/cache-audit/SKILL.md protocols/verdict-catalog.md protocols/skill-directory.md
git add skills/cache-audit/SKILL.md protocols/verdict-catalog.md protocols/skill-directory.md

staged=$(git diff --cached --name-only)
if echo "$staged" | grep -q 'skills/cache-audit/SKILL.md'; then
  if echo "$staged" | grep -q 'protocols/verdict-catalog.md' \
     && echo "$staged" | grep -q 'protocols/skill-directory.md'; then
    echo "  ok: CASE1 atomic-three-staged passes"; PASS=$((PASS + 1))
  else
    echo "  FAIL: CASE1 missing companions"; FAIL=$((FAIL + 1))
  fi
fi

# CASE 2 — SKILL.md staged alone (no catalog/dir): FAIL guard fires.
git reset -q
git add skills/cache-audit/SKILL.md
staged=$(git diff --cached --name-only)
if echo "$staged" | grep -q 'skills/cache-audit/SKILL.md'; then
  if echo "$staged" | grep -q 'protocols/verdict-catalog.md' \
     && echo "$staged" | grep -q 'protocols/skill-directory.md'; then
    echo "  FAIL: CASE2 should have failed atomic guard"; FAIL=$((FAIL + 1))
  else
    echo "  ok: CASE2 atomic-skill-alone trips guard (companions absent)"; PASS=$((PASS + 1))
  fi
fi

# CASE 3 — neither staged: no-op (guard only fires when SKILL.md staged).
git reset -q
git add protocols/verdict-catalog.md
staged=$(git diff --cached --name-only)
if echo "$staged" | grep -q 'skills/cache-audit/SKILL.md'; then
  echo "  FAIL: CASE3 SKILL.md leaked into staged set"; FAIL=$((FAIL + 1))
else
  echo "  ok: CASE3 no-skill-staged is no-op for atomic gate"; PASS=$((PASS + 1))
fi

# CASE 4 — assert THIS commit's actual staged set (or last commit on the
# build branch) reflects the invariant. Look at the most recent commit
# touching skills/cache-audit/SKILL.md in REPO_ROOT — that commit MUST
# also contain verdict-catalog.md (at any path, basename match tolerates
# both old rules/ and new protocols/ locations) and protocols/skill-directory.md.
cd "$REPO_ROOT"
LAST_COMMIT=$(git log -n 1 --format=%H -- skills/cache-audit/SKILL.md 2>/dev/null || echo "")
if [ -z "$LAST_COMMIT" ]; then
  echo "  ok: CASE4 no commit yet touches skills/cache-audit/SKILL.md (build pre-commit)"; PASS=$((PASS + 1))
else
  COMMITTED_PATHS=$(git diff-tree --no-commit-id --name-only -r "$LAST_COMMIT")
  if echo "$COMMITTED_PATHS" | grep -q 'verdict-catalog.md' \
     && echo "$COMMITTED_PATHS" | grep -q 'protocols/skill-directory.md'; then
    echo "  ok: CASE4 commit $LAST_COMMIT contains all three companions"; PASS=$((PASS + 1))
  else
    echo "  FAIL: CASE4 commit $LAST_COMMIT missing companion(s):"
    echo "$COMMITTED_PATHS" | sed 's/^/    /'
    FAIL=$((FAIL + 1))
  fi
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
