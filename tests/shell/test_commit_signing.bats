#!/usr/bin/env bats
# CI-gating tests for hooks/_lib/commit-signing.sh + worktree-create.sh wire-in.
# Mirrors hooks/tests/test-commit-signing.sh (local-only); CI globs tests/shell/*.bats.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  # shellcheck source=/dev/null
  source "$REPO_ROOT/hooks/_lib/commit-signing.sh"
  CS_TMP="$(mktemp -d)"
  CS_REPO="$CS_TMP/repo"
  git init -q "$CS_REPO"
  git -C "$CS_REPO" config user.email "test@example.com"
  git -C "$CS_REPO" config user.name "Test"
  git -C "$CS_REPO" config commit.gpgsign false
  git -C "$CS_REPO" commit -q --allow-empty -m init
}

teardown() {
  [ -n "${CS_TMP:-}" ] && rm -rf "$CS_TMP"
}

@test "signing OFF -> _cs_verify_reachable returns 0" {
  run _cs_verify_reachable "$CS_REPO"
  [ "$status" -eq 0 ]
}

@test "ssh signing ON + missing key -> rc 1 with reason (fail-closed)" {
  git -C "$CS_REPO" config commit.gpgsign true
  git -C "$CS_REPO" config gpg.format ssh
  git -C "$CS_REPO" config user.signingkey "$CS_TMP/no-such-key"
  run _cs_verify_reachable "$CS_REPO"
  [ "$status" -eq 1 ]
  [ -n "$output" ]
}

@test "ssh signing ON + readable key -> rc 0" {
  printf 'fake\n' > "$CS_TMP/id_sign"
  git -C "$CS_REPO" config commit.gpgsign true
  git -C "$CS_REPO" config gpg.format ssh
  git -C "$CS_REPO" config user.signingkey "$CS_TMP/id_sign"
  run _cs_verify_reachable "$CS_REPO"
  [ "$status" -eq 0 ]
}

@test "openpgp signing ON + signingkey unset -> rc 1 with reason (fail-closed)" {
  git -C "$CS_REPO" config commit.gpgsign true
  git -C "$CS_REPO" config gpg.format openpgp
  run _cs_verify_reachable "$CS_REPO"
  [ "$status" -eq 1 ]
  [ -n "$output" ]
}

@test "worktree-create.sh signing OFF -> stdout is exactly the worktree path" {
  local main="$CS_TMP/e2e-main"
  git init -q "$main"
  git -C "$main" config user.email "test@example.com"
  git -C "$main" config user.name "Test"
  git -C "$main" config commit.gpgsign false
  git -C "$main" commit -q --allow-empty -m init
  local wt="$main/.claude/worktrees/agent-cs-e2e"
  mkdir -p "$main/.claude/worktrees"
  run bash -c "jq -nc --arg p '$wt' --arg r '$main' --arg b 'worktree-cs-e2e' \
    '{tool_input:{path:\$p,repo_root:\$r,branch:\$b}}' \
    | bash '$REPO_ROOT/hooks/worktree-create.sh' 2>/dev/null"
  [ "$status" -eq 0 ]
  [ "$output" = "$wt" ]
  git -C "$main" worktree remove --force "$wt" 2>/dev/null || true
}

@test "test-commit-signing.sh harness exits 0" {
  run bash "$REPO_ROOT/hooks/tests/test-commit-signing.sh"
  [ "$status" -eq 0 ]
}
