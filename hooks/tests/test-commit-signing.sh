#!/usr/bin/env bash
# Tests for hooks/_lib/commit-signing.sh and the worktree-create.sh wire-in.
# CI mirror: tests/shell/test_commit_signing.bats (CI gates on the .bats, not this).
#
# Run from repo root: bash hooks/tests/test-commit-signing.sh
# Exit 0 if all pass, exit 1 if any fail.

set -uo pipefail

HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=/dev/null
source "$HOOKS_DIR/_lib/commit-signing.sh"

PASS=0
FAIL=0
pass() { echo "  PASS: $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL: $1 ($2)"; FAIL=$((FAIL + 1)); }

echo "=== commit-signing Test Harness ==="
echo ""

# -- Syntax check -------------------------------------------------------------
echo "-- syntax --"
if bash -n "$HOOKS_DIR/_lib/commit-signing.sh" > /dev/null 2>&1; then
  pass "commit-signing.sh syntax valid"
else
  fail "commit-signing.sh syntax valid" "bash -n failed"
fi
if bash -n "$HOOKS_DIR/worktree-create.sh" > /dev/null 2>&1; then
  pass "worktree-create.sh syntax valid"
else
  fail "worktree-create.sh syntax valid" "bash -n failed"
fi

# Hermetic scratch repo (no signing configured by default).
CS_TMP=$(mktemp -d)
CS_REPO="$CS_TMP/repo"
git init -q "$CS_REPO"
git -C "$CS_REPO" commit -q --allow-empty -m init

# -- signing OFF -> reachable returns 0 ---------------------------------------
echo "-- signing OFF --"
if _cs_verify_reachable "$CS_REPO" >/dev/null; then
  pass "signing OFF -> _cs_verify_reachable returns 0"
else
  fail "signing OFF -> _cs_verify_reachable returns 0" "returned non-zero"
fi

# -- ssh signing ON, readable key file -> returns 0 ---------------------------
echo "-- ssh signing, readable key --"
CS_KEY="$CS_TMP/id_sign"
printf 'fake-key-material\n' > "$CS_KEY"
git -C "$CS_REPO" config commit.gpgsign true
git -C "$CS_REPO" config gpg.format ssh
git -C "$CS_REPO" config user.signingkey "$CS_KEY"
if _cs_verify_reachable "$CS_REPO" >/dev/null; then
  pass "ssh signing ON + readable key -> returns 0"
else
  fail "ssh signing ON + readable key -> returns 0" "returned non-zero"
fi

# -- ssh signing ON, MISSING key file -> returns 1 + reason (fail-closed) ------
echo "-- ssh signing, missing key (fail-closed) --"
git -C "$CS_REPO" config user.signingkey "$CS_TMP/does-not-exist"
CS_OUT=$(_cs_verify_reachable "$CS_REPO")
CS_RC=$?
if [[ "$CS_RC" -eq 1 && -n "$CS_OUT" ]]; then
  pass "ssh signing ON + missing key -> returns 1 with reason"
else
  fail "ssh signing ON + missing key -> returns 1 with reason" "rc=$CS_RC out='$CS_OUT'"
fi

# -- openpgp signing ON, signingkey UNSET -> returns 1 + reason ----------------
echo "-- openpgp signing, signingkey unset (fail-closed) --"
git -C "$CS_REPO" config commit.gpgsign true
git -C "$CS_REPO" config gpg.format openpgp
git -C "$CS_REPO" config --unset user.signingkey
CS_OUT=$(_cs_verify_reachable "$CS_REPO")
CS_RC=$?
if [[ "$CS_RC" -eq 1 && -n "$CS_OUT" ]]; then
  pass "openpgp signing ON + signingkey unset -> returns 1 with reason"
else
  fail "openpgp signing ON + signingkey unset -> returns 1 with reason" "rc=$CS_RC out='$CS_OUT'"
fi

# -- worktree-create.sh end-to-end: signing OFF -> stdout is exactly the path --
echo "-- worktree-create.sh stdout-clean (signing OFF) --"
CS_MAIN="$CS_TMP/e2e-main"
git init -q "$CS_MAIN"
git -C "$CS_MAIN" commit -q --allow-empty -m init
CS_WT="$CS_MAIN/.claude/worktrees/agent-cs-e2e"
mkdir -p "$CS_MAIN/.claude/worktrees"
CS_STDOUT=$(jq -nc --arg p "$CS_WT" --arg r "$CS_MAIN" --arg b "worktree-cs-e2e" \
  '{tool_input:{path:$p,repo_root:$r,branch:$b}}' \
  | bash "$HOOKS_DIR/worktree-create.sh" 2>/dev/null)
if [[ "$CS_STDOUT" == "$CS_WT" ]]; then
  pass "worktree-create.sh signing OFF -> stdout is exactly the worktree path"
else
  fail "worktree-create.sh signing OFF -> stdout is exactly the worktree path" "stdout='$CS_STDOUT'"
fi
git -C "$CS_MAIN" worktree remove --force "$CS_WT" 2>/dev/null

rm -rf "$CS_TMP"

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[[ $FAIL -gt 0 ]] && exit 1
exit 0
