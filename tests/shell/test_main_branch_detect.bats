#!/usr/bin/env bats
# Slice 1 — main-branch-detect lib: forbidden/allowed matrix + fixture helpers.
# Sources both main-branch-detect.sh (runtime regex) and main-branch-detect-fixtures.sh
# (test-only helpers). Hermetic — no real $HOME, no real repo mutation.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  source "$REPO_ROOT/hooks/_lib/main-branch-detect.sh"
  source "$REPO_ROOT/hooks/_lib/main-branch-detect-fixtures.sh"
  TMP_REPO="$(mktemp -d)"
}

teardown() {
  rm -rf "$TMP_REPO"
}

# Helper: assert is_forbidden_command returns 0 (forbidden) for the given cmd.
_assert_forbidden() {
  run is_forbidden_command "$1"
  [ "$status" -eq 0 ] || { echo "expected forbidden but allowed: $1"; return 1; }
}

# Helper: assert is_forbidden_command returns 1 (allowed) for the given cmd.
_assert_allowed() {
  run is_forbidden_command "$1"
  [ "$status" -eq 1 ] || { echo "expected allowed but forbidden: $1"; return 1; }
}

# ---------------------------------------------------------------------------
# AC1.1 — is_in_main_tree fixture helper
# ---------------------------------------------------------------------------

@test "T1 is_in_main_tree returns 0 from main tree of hermetic repo" {
  ( cd "$TMP_REPO" && git init -q -b main )
  ( cd "$TMP_REPO" && git config user.email t@t && git config user.name t )
  ( cd "$TMP_REPO" && git commit -q --allow-empty -m init )
  run is_in_main_tree "$TMP_REPO"
  [ "$status" -eq 0 ]
}

@test "T1b is_in_main_tree returns 1 from a worktree" {
  ( cd "$TMP_REPO" && git init -q -b main )
  ( cd "$TMP_REPO" && git config user.email t@t && git config user.name t )
  ( cd "$TMP_REPO" && git commit -q --allow-empty -m init )
  WT="$(mktemp -d)/wt"
  ( cd "$TMP_REPO" && git worktree add -q -b feat/x "$WT" )
  run is_in_main_tree "$WT"
  [ "$status" -eq 1 ]
  run is_in_worktree "$WT"
  [ "$status" -eq 0 ]
  rm -rf "$(dirname "$WT")"
}

# ---------------------------------------------------------------------------
# AC1.2 positive matrix — forbidden bare forms (T2-T24)
# ---------------------------------------------------------------------------

@test "T2  forbidden: git checkout foo"                              { _assert_forbidden 'git checkout foo'; }
@test "T3  forbidden: git\\tcheckout foo (tab)"                      { _assert_forbidden $'git\tcheckout foo'; }
@test "T4  forbidden: git  checkout foo (multi-space)"               { _assert_forbidden 'git  checkout foo'; }
@test "T5  forbidden: git checkout -b foo"                           { _assert_forbidden 'git checkout -b foo'; }
@test "T6  forbidden: git switch foo"                                { _assert_forbidden 'git switch foo'; }
@test "T7  forbidden: git switch -c foo"                             { _assert_forbidden 'git switch -c foo'; }
@test "T8  forbidden: git branch -d foo"                             { _assert_forbidden 'git branch -d foo'; }
@test "T9  forbidden: git branch -D foo"                             { _assert_forbidden 'git branch -D foo'; }
@test "T10 forbidden: git reset --hard HEAD"                         { _assert_forbidden 'git reset --hard HEAD'; }
@test "T11 forbidden: git merge feature/x"                           { _assert_forbidden 'git merge feature/x'; }
@test "T12 forbidden: git rebase main"                               { _assert_forbidden 'git rebase main'; }
@test "T13 forbidden: git pull"                                      { _assert_forbidden 'git pull'; }
@test "T14 forbidden: git pull origin main"                          { _assert_forbidden 'git pull origin main'; }
@test "T15 forbidden: git fetch origin main:main"                    { _assert_forbidden 'git fetch origin main:main'; }
@test "T16 forbidden: git fetch origin pull/123/head:pr-123"         { _assert_forbidden 'git fetch origin pull/123/head:pr-123'; }
@test "T17 forbidden: git push origin HEAD:main"                     { _assert_forbidden 'git push origin HEAD:main'; }
@test "T18 forbidden: git push origin foo:main"                      { _assert_forbidden 'git push origin foo:main'; }
@test "T19 forbidden: gh pr create"                                  { _assert_forbidden 'gh pr create'; }
@test "T20 forbidden: gh pr create --title x --body y"               { _assert_forbidden 'gh pr create --title x --body y'; }
@test "T21 forbidden compound: git status && git checkout foo"       { _assert_forbidden 'git status && git checkout foo'; }
@test "T22 forbidden compound: git checkout foo; git status"         { _assert_forbidden 'git checkout foo; git status'; }
@test "T23 forbidden compound: git checkout foo || true"             { _assert_forbidden 'git checkout foo || true'; }
@test "T24 forbidden pipeline: echo x | git checkout foo"            { _assert_forbidden 'echo x | git checkout foo'; }

# ---------------------------------------------------------------------------
# AC1.2 negative matrix — allowed/delegated forms (T25-T40)
# ---------------------------------------------------------------------------

@test "T25 allowed: git -C /tmp/wt checkout foo"                     { _assert_allowed 'git -C /tmp/wt checkout foo'; }
@test "T26 allowed: git --git-dir=/tmp/.git checkout foo"            { _assert_allowed 'git --git-dir=/tmp/.git checkout foo'; }
@test "T27 allowed: cd /tmp && git checkout foo"                     { _assert_allowed 'cd /tmp && git checkout foo'; }
@test "T28 allowed: (cd /tmp && git checkout foo)"                   { _assert_allowed '(cd /tmp && git checkout foo)'; }
@test "T29 allowed: (cd \"\$WT\" && gh pr create --title x)"          { _assert_allowed '(cd "$WT" && gh pr create --title x)'; }
@test "T30 allowed: cd \"\$WT\" && gh pr create --title x"            { _assert_allowed 'cd "$WT" && gh pr create --title x'; }
@test "T31 allowed: git status"                                      { _assert_allowed 'git status'; }
@test "T32 allowed: git log --oneline -5"                            { _assert_allowed 'git log --oneline -5'; }
@test "T33 allowed: git diff --stat"                                 { _assert_allowed 'git diff --stat'; }
@test "T34 allowed: git fetch origin (no refspec)"                   { _assert_allowed 'git fetch origin'; }
@test "T35 allowed: git fetch --all"                                 { _assert_allowed 'git fetch --all'; }
@test "T36 allowed: git fetch origin +refs/heads/*:refs/remotes/...." { _assert_allowed 'git fetch origin +refs/heads/*:refs/remotes/origin/*'; }
@test "T37 allowed: git worktree add /tmp/wt -b foo main"            { _assert_allowed 'git worktree add /tmp/wt -b foo main'; }
@test "T38 allowed: git push origin feature/foo"                     { _assert_allowed 'git push origin feature/foo'; }
@test "T39 allowed: git add file.txt && git commit -m x"             { _assert_allowed 'git add file.txt && git commit -m x'; }
@test "T40 allowed: git commit -m x"                                 { _assert_allowed 'git commit -m x'; }

# ---------------------------------------------------------------------------
# AC1.2 special cases (T41-T43) — fetch refspec edges + ;-not-delegation
# ---------------------------------------------------------------------------

@test "T41 forbidden: cd /tmp; git checkout foo (semicolon != delegation)" {
  _assert_forbidden 'cd /tmp; git checkout foo'
}

@test "T42 forbidden: git fetch origin pull/123/head:pr-123 (local-ref refspec)" {
  _assert_forbidden 'git fetch origin pull/123/head:pr-123'
}

@test "T43 allowed: git fetch origin +refs/heads/*:refs/remotes/origin/* (remote-tracking)" {
  _assert_allowed 'git fetch origin +refs/heads/*:refs/remotes/origin/*'
}
