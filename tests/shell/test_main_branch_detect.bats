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
@test "T8  forbidden: git branch -d main (deleting checked-out branch)" {
  ( cd "$TMP_REPO" && git init -q -b main )
  ( cd "$TMP_REPO" && git config user.email t@t && git config user.name t )
  ( cd "$TMP_REPO" && git commit -q --allow-empty -m init )
  ( cd "$TMP_REPO" && _assert_forbidden 'git branch -d main' )
}
@test "T9  forbidden: git branch -D main (force-deleting checked-out branch)" {
  ( cd "$TMP_REPO" && git init -q -b main )
  ( cd "$TMP_REPO" && git config user.email t@t && git config user.name t )
  ( cd "$TMP_REPO" && git commit -q --allow-empty -m init )
  ( cd "$TMP_REPO" && _assert_forbidden 'git branch -D main' )
}
@test "T10 forbidden: git reset --hard HEAD"                         { _assert_forbidden 'git reset --hard HEAD'; }
@test "T11 forbidden: git merge feature/x"                           { _assert_forbidden 'git merge feature/x'; }
@test "T12 forbidden: git rebase main"                               { _assert_forbidden 'git rebase main'; }
@test "T13 allowed: git pull"                                        { _assert_allowed 'git pull'; }
@test "T14 allowed: git pull origin main"                            { _assert_allowed 'git pull origin main'; }
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

@test "T25 allowed: git -C <registered-wt> checkout foo" {
  ( cd "$TMP_REPO" && git init -q -b main )
  ( cd "$TMP_REPO" && git config user.email t@t && git config user.name t )
  ( cd "$TMP_REPO" && git commit -q --allow-empty -m init )
  local WT; WT="$(mktemp -d)/wt"
  ( cd "$TMP_REPO" && git worktree add -q -b feat/x "$WT" )
  CLAUDE_WORKTREE_PATH="$WT" _assert_allowed "git -C $WT checkout foo"
  rm -rf "$(dirname "$WT")"
}
@test "T26 allowed: git --git-dir=/tmp/.git checkout foo"            { _assert_allowed 'git --git-dir=/tmp/.git checkout foo'; }
@test "T27 allowed: cd <registered-wt> && git checkout foo" {
  ( cd "$TMP_REPO" && git init -q -b main )
  ( cd "$TMP_REPO" && git config user.email t@t && git config user.name t )
  ( cd "$TMP_REPO" && git commit -q --allow-empty -m init )
  local WT; WT="$(mktemp -d)/wt"
  ( cd "$TMP_REPO" && git worktree add -q -b feat/x "$WT" )
  CLAUDE_WORKTREE_PATH="$WT" _assert_allowed "cd $WT && git checkout foo"
  rm -rf "$(dirname "$WT")"
}
@test "T28 allowed: (cd <registered-wt> && git checkout foo)" {
  ( cd "$TMP_REPO" && git init -q -b main )
  ( cd "$TMP_REPO" && git config user.email t@t && git config user.name t )
  ( cd "$TMP_REPO" && git commit -q --allow-empty -m init )
  local WT; WT="$(mktemp -d)/wt"
  ( cd "$TMP_REPO" && git worktree add -q -b feat/x "$WT" )
  CLAUDE_WORKTREE_PATH="$WT" _assert_allowed "(cd $WT && git checkout foo)"
  rm -rf "$(dirname "$WT")"
}
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

# ---------------------------------------------------------------------------
# R1 fixes — review-driven matrix extension
# ---------------------------------------------------------------------------

# Finding #1 (HIGH code) — multi-clause bypass: `git -C` / `--git-dir=` are
# self-contained on a single clause and MUST NOT carry delegation across `&&`.
@test "T44 forbidden: git -C /tmp/wt status && git checkout main"        { _assert_forbidden 'git -C /tmp/wt status && git checkout main'; }
@test "T45 forbidden: git --git-dir=/tmp/.git status && git checkout main" { _assert_forbidden 'git --git-dir=/tmp/.git status && git checkout main'; }
@test "T46 allowed: cd <registered-wt> && git status && git checkout main (cd persists)" {
  ( cd "$TMP_REPO" && git init -q -b main )
  ( cd "$TMP_REPO" && git config user.email t@t && git config user.name t )
  ( cd "$TMP_REPO" && git commit -q --allow-empty -m init )
  local WT; WT="$(mktemp -d)/wt"
  ( cd "$TMP_REPO" && git worktree add -q -b feat/x "$WT" )
  CLAUDE_WORKTREE_PATH="$WT" _assert_allowed "cd $WT && git status && git checkout main"
  rm -rf "$(dirname "$WT")"
}
@test "T47 allowed: cd <registered-wt> && git status && gh pr create --title x" {
  ( cd "$TMP_REPO" && git init -q -b main )
  ( cd "$TMP_REPO" && git config user.email t@t && git config user.name t )
  ( cd "$TMP_REPO" && git commit -q --allow-empty -m init )
  local WT; WT="$(mktemp -d)/wt"
  ( cd "$TMP_REPO" && git worktree add -q -b feat/x "$WT" )
  CLAUDE_WORKTREE_PATH="$WT" _assert_allowed "cd $WT && git status && gh pr create --title x"
  rm -rf "$(dirname "$WT")"
}

# CRITICAL-1 (security) — delete-remote-main via empty-source refspec.
@test "T48 forbidden: git push origin :main (delete-remote)"             { _assert_forbidden 'git push origin :main'; }
@test "T49 forbidden: git push origin +:main (forced delete-remote)"     { _assert_forbidden 'git push origin +:main'; }
@test "T50 forbidden: git push origin :refs/heads/main (qualified delete)" { _assert_forbidden 'git push origin :refs/heads/main'; }

# CRITICAL-2 (security) — delete-remote-main via --delete / -d flags.
@test "T51 forbidden: git push origin --delete main"                     { _assert_forbidden 'git push origin --delete main'; }
@test "T52 forbidden: git push origin -d main"                           { _assert_forbidden 'git push origin -d main'; }
@test "T53 forbidden: git push --delete origin main"                     { _assert_forbidden 'git push --delete origin main'; }

# CRITICAL-3 (security) — direct ref rewrites bypass checkout/switch entirely.
@test "T54 forbidden: git update-ref refs/heads/main HEAD"               { _assert_forbidden 'git update-ref refs/heads/main HEAD'; }
@test "T55 forbidden: git update-ref refs/heads/main abc123def"          { _assert_forbidden 'git update-ref refs/heads/main abc123def'; }
@test "T56 forbidden: git symbolic-ref HEAD refs/heads/feat/x"           { _assert_forbidden 'git symbolic-ref HEAD refs/heads/feat/x'; }
@test "T57 allowed: git update-ref refs/heads/feature-x HEAD"            { _assert_allowed 'git update-ref refs/heads/feature-x HEAD'; }

# HIGH-1 (security) — wrapper bypass: defer execution to bypass regex match.
@test "T58 forbidden: bash -c 'git checkout main'"                       { _assert_forbidden "bash -c 'git checkout main'"; }
@test "T59 forbidden: sh -c 'git checkout main'"                         { _assert_forbidden "sh -c 'git checkout main'"; }
@test "T60 forbidden: eval 'git checkout main'"                          { _assert_forbidden "eval 'git checkout main'"; }
@test "T61 forbidden: xargs git checkout"                                { _assert_forbidden 'xargs git checkout'; }
@test "T62 forbidden: find -exec git checkout" {
  _assert_forbidden 'find . -name x -exec git checkout HEAD ;'
}
@test "T63 allowed: bash hook.sh (no -c form)"                           { _assert_allowed 'bash hook.sh'; }

# HIGH-2 (security) — env-prefix and absolute-path bypass.
@test "T64 forbidden: GIT_DIR=/tmp/x git checkout main"                  { _assert_forbidden 'GIT_DIR=/tmp/x git checkout main'; }
@test "T65 forbidden: GIT_DIR=/tmp/x GIT_INDEX_FILE=/tmp/i git checkout main" { _assert_forbidden 'GIT_DIR=/tmp/x GIT_INDEX_FILE=/tmp/i git checkout main'; }
@test "T66 forbidden: /usr/bin/git checkout main"                        { _assert_forbidden '/usr/bin/git checkout main'; }
@test "T67 forbidden: /opt/homebrew/bin/git checkout main"               { _assert_forbidden '/opt/homebrew/bin/git checkout main'; }
@test "T68 allowed: GIT_AUTHOR_NAME=Bot git status"                      { _assert_allowed 'GIT_AUTHOR_NAME=Bot git status'; }

# HIGH-3 (security) — multi-refspec fetch: any destination resolving to main is forbidden.
@test "T69 forbidden: git fetch origin foo:bar main:main"                { _assert_forbidden 'git fetch origin foo:bar main:main'; }
@test "T70 forbidden: git fetch origin a:refs/remotes/origin/x main:refs/heads/main" { _assert_forbidden 'git fetch origin a:refs/remotes/origin/x main:refs/heads/main'; }
@test "T71 allowed: git fetch origin a:refs/remotes/origin/a b:refs/remotes/origin/b" { _assert_allowed 'git fetch origin a:refs/remotes/origin/a b:refs/remotes/origin/b'; }

# HIGH-4 (security) — git -c <opt> rebase|merge|reset|checkout|switch must be blocked.
@test "T72 forbidden: git -c rebase.autoStash=true rebase main"          { _assert_forbidden 'git -c rebase.autoStash=true rebase main'; }
@test "T73 forbidden: git -c core.editor=vi -c color.ui=auto checkout main" { _assert_forbidden 'git -c core.editor=vi -c color.ui=auto checkout main'; }
@test "T74 forbidden: git -c merge.tool=vimdiff merge feat"              { _assert_forbidden 'git -c merge.tool=vimdiff merge feat'; }
@test "T75 allowed: git -c color.ui=auto status"                         { _assert_allowed 'git -c color.ui=auto status'; }

# Pull carve-out — `git pull` to update main is safe; only non-main branch arg blocks.
@test "T76 allowed: git pull --rebase"                                   { _assert_allowed 'git pull --rebase'; }
@test "T77 allowed: git pull --rebase origin main"                       { _assert_allowed 'git pull --rebase origin main'; }
@test "T78 allowed: git pull origin"                                     { _assert_allowed 'git pull origin'; }
@test "T79 forbidden: git pull origin feature-branch"                    { _assert_forbidden 'git pull origin feature-branch'; }

# ---------------------------------------------------------------------------
# Slice 3 — branch-delete and merge --ff-only carve-outs (T80–T89)
# ---------------------------------------------------------------------------

@test "T80 allowed: git branch -d old-feature from repo-root on main (bare-cwd leg, no CLAUDE_WORKTREE_PATH)" {
  # Production scenario: orchestrator cleanup runs git branch -D merged-branch from repo root.
  # CLAUDE_WORKTREE_PATH is NOT set; bare git rev-parse resolves from cwd.
  ( cd "$TMP_REPO" && git init -q -b main )
  ( cd "$TMP_REPO" && git config user.email t@t && git config user.name t )
  ( cd "$TMP_REPO" && git commit -q --allow-empty -m init )
  ( cd "$TMP_REPO" && git branch old-feature )
  ( cd "$TMP_REPO" && unset CLAUDE_WORKTREE_PATH && _assert_allowed 'git branch -d old-feature' )
}

@test "T81 allowed: git branch -D old-feature force-delete from repo-root on main (bare-cwd leg)" {
  ( cd "$TMP_REPO" && git init -q -b main )
  ( cd "$TMP_REPO" && git config user.email t@t && git config user.name t )
  ( cd "$TMP_REPO" && git commit -q --allow-empty -m init )
  ( cd "$TMP_REPO" && git branch old-feature )
  ( cd "$TMP_REPO" && unset CLAUDE_WORKTREE_PATH && _assert_allowed 'git branch -D old-feature' )
}

@test "T81b allowed: git branch -d old-feature via CLAUDE_WORKTREE_PATH (agent-dispatch leg)" {
  ( cd "$TMP_REPO" && git init -q -b main )
  ( cd "$TMP_REPO" && git config user.email t@t && git config user.name t )
  ( cd "$TMP_REPO" && git commit -q --allow-empty -m init )
  ( cd "$TMP_REPO" && git branch old-feature )
  ( CLAUDE_WORKTREE_PATH="$TMP_REPO" _assert_allowed 'git branch -d old-feature' )
}

@test "T82 forbidden: git branch -d from non-git dir (fail-closed — bare git rev-parse yields empty)" {
  local NON_GIT_DIR; NON_GIT_DIR="$(mktemp -d)"
  ( cd "$NON_GIT_DIR" && unset CLAUDE_WORKTREE_PATH && _assert_forbidden 'git branch -d old-feature' )
  rm -rf "$NON_GIT_DIR"
}

@test "T83 forbidden: git branch -d main when current branch is main (via CLAUDE_WORKTREE_PATH)" {
  ( cd "$TMP_REPO" && git init -q -b main )
  ( cd "$TMP_REPO" && git config user.email t@t && git config user.name t )
  ( cd "$TMP_REPO" && git commit -q --allow-empty -m init )
  ( CLAUDE_WORKTREE_PATH="$TMP_REPO" _assert_forbidden 'git branch -d main' )
}

@test "T83b forbidden: git branch -d main from repo-root on main (bare-cwd leg)" {
  ( cd "$TMP_REPO" && git init -q -b main )
  ( cd "$TMP_REPO" && git config user.email t@t && git config user.name t )
  ( cd "$TMP_REPO" && git commit -q --allow-empty -m init )
  ( cd "$TMP_REPO" && unset CLAUDE_WORKTREE_PATH && _assert_forbidden 'git branch -d main' )
}

@test "T83c forbidden: git branch -D main from feature-branch worktree (protected-by-name)" {
  ( cd "$TMP_REPO" && git init -q -b main )
  ( cd "$TMP_REPO" && git config user.email t@t && git config user.name t )
  ( cd "$TMP_REPO" && git commit -q --allow-empty -m init )
  ( cd "$TMP_REPO" && git checkout -q -b feature/x )
  ( CLAUDE_WORKTREE_PATH="$TMP_REPO" _assert_forbidden 'git branch -D main' )
}

@test "T83d forbidden: git branch -d main feature (multi-name, main is protected)" {
  ( cd "$TMP_REPO" && git init -q -b main )
  ( cd "$TMP_REPO" && git config user.email t@t && git config user.name t )
  ( cd "$TMP_REPO" && git commit -q --allow-empty -m init )
  ( cd "$TMP_REPO" && git branch feature )
  ( cd "$TMP_REPO" && unset CLAUDE_WORKTREE_PATH && _assert_forbidden 'git branch -d main feature' )
}

@test "T84 allowed: git merge --ff-only origin/main"                     { _assert_allowed 'git merge --ff-only origin/main'; }
@test "T85 allowed: git merge --ff-only main"                            { _assert_allowed 'git merge --ff-only main'; }
@test "T86 allowed: git merge --ff-only upstream/main"                   { _assert_allowed 'git merge --ff-only upstream/main'; }
@test "T87 forbidden: git merge --ff-only (bare, no target — merges FETCH_HEAD)" { _assert_forbidden 'git merge --ff-only'; }
@test "T88 forbidden: git merge --ff-only feature/x (non-main target)"   { _assert_forbidden 'git merge --ff-only feature/x'; }
@test "T89 allowed: git merge --ff-only origin"                          { _assert_allowed 'git merge --ff-only origin'; }

# ---------------------------------------------------------------------------
# Delegation-target validation (T90-T100) — fix for REPO_ROOT bypass
# ---------------------------------------------------------------------------

@test "T90 forbidden: cd <REPO_ROOT_literal> && git checkout -b x (REPO_ROOT path)" {
  ( cd "$TMP_REPO" && git init -q -b main )
  ( cd "$TMP_REPO" && git config user.email t@t && git config user.name t )
  ( cd "$TMP_REPO" && git commit -q --allow-empty -m init )
  CLAUDE_WORKTREE_PATH="" _assert_forbidden "cd $TMP_REPO && git checkout -b x"
}

@test "T91 forbidden: git -C . checkout -b x (dot resolves to cwd = REPO_ROOT)" {
  ( cd "$TMP_REPO" && git init -q -b main )
  ( cd "$TMP_REPO" && git config user.email t@t && git config user.name t )
  ( cd "$TMP_REPO" && git commit -q --allow-empty -m init )
  ( cd "$TMP_REPO" && _assert_forbidden 'git -C . checkout -b x' )
}

@test "T92 forbidden: git -C \"\" checkout x (empty target after dequote)" {
  _assert_forbidden 'git -C "" checkout x'
}

@test "T93 allowed: git -C \"\$WORKTREE\" checkout foo (variable-ref passthrough)" {
  _assert_allowed 'git -C "$WORKTREE" checkout foo'
}

@test "T94 allowed: cd \"\$WORKTREE\" && git checkout foo (variable-ref passthrough)" {
  _assert_allowed 'cd "$WORKTREE" && git checkout foo'
}

@test "T95 allowed: git -C <registered-wt> checkout foo (real registered worktree)" {
  ( cd "$TMP_REPO" && git init -q -b main )
  ( cd "$TMP_REPO" && git config user.email t@t && git config user.name t )
  ( cd "$TMP_REPO" && git commit -q --allow-empty -m init )
  local WT; WT="$(mktemp -d)/wt"
  ( cd "$TMP_REPO" && git worktree add -q -b feat/x "$WT" )
  CLAUDE_WORKTREE_PATH="$WT" _assert_allowed "git -C $WT checkout foo"
  rm -rf "$(dirname "$WT")"
}

@test "T96 allowed: cd <registered-wt> && git checkout foo && git checkout feat/y (cd persists)" {
  ( cd "$TMP_REPO" && git init -q -b main )
  ( cd "$TMP_REPO" && git config user.email t@t && git config user.name t )
  ( cd "$TMP_REPO" && git commit -q --allow-empty -m init )
  local WT; WT="$(mktemp -d)/wt"
  ( cd "$TMP_REPO" && git worktree add -q -b feat/x "$WT" )
  CLAUDE_WORKTREE_PATH="$WT" _assert_allowed "cd $WT && git checkout foo && git checkout feat/y"
  rm -rf "$(dirname "$WT")"
}

@test "T97 forbidden: git -C <registered-wt> status && git checkout main (git-C scoped to clause)" {
  ( cd "$TMP_REPO" && git init -q -b main )
  ( cd "$TMP_REPO" && git config user.email t@t && git config user.name t )
  ( cd "$TMP_REPO" && git commit -q --allow-empty -m init )
  local WT; WT="$(mktemp -d)/wt"
  ( cd "$TMP_REPO" && git worktree add -q -b feat/x "$WT" )
  CLAUDE_WORKTREE_PATH="$WT" _assert_forbidden "git -C $WT status && git checkout main"
  rm -rf "$(dirname "$WT")"
}

@test "T98 forbidden: git -C <unregistered-dir> checkout foo (not in worktree list)" {
  ( cd "$TMP_REPO" && git init -q -b main )
  ( cd "$TMP_REPO" && git config user.email t@t && git config user.name t )
  ( cd "$TMP_REPO" && git commit -q --allow-empty -m init )
  local UNREGISTERED; UNREGISTERED="$(mktemp -d)"
  _assert_forbidden "git -C $UNREGISTERED checkout foo"
  rm -rf "$UNREGISTERED"
}

@test "T99 forbidden: cd <unregistered-dir> && git checkout foo (falls through; verb caught)" {
  local UNREGISTERED; UNREGISTERED="$(mktemp -d)"
  _assert_forbidden "cd $UNREGISTERED && git checkout foo"
  rm -rf "$UNREGISTERED"
}

@test "T100 forbidden: git -C '\"\"' checkout -b x (double-empty-dequote edge)" {
  _assert_forbidden "git -C '\"\"' checkout -b x"
}

# ---------------------------------------------------------------------------
# H1 — fail-CLOSED when python3 is absent (T101)
# ---------------------------------------------------------------------------

@test "T101 fail-closed contract: _mbd_target_is_valid_worktree returns non-zero for literal REPO_ROOT" {
  # Verifies H1 fix: _mbd_target_is_valid_worktree must DENY a REPO_ROOT path.
  # (When python3 is absent, the old `|| return 0` would allow it; the fix uses
  # `|| return 1` so any inability to resolve canonical path = deny.)
  ( cd "$TMP_REPO" && git init -q -b main )
  ( cd "$TMP_REPO" && git config user.email t@t && git config user.name t )
  ( cd "$TMP_REPO" && git commit -q --allow-empty -m init )
  # Direct unit test: REPO_ROOT path must return non-zero (denied).
  run _mbd_target_is_valid_worktree "$TMP_REPO"
  [ "$status" -ne 0 ]
}

@test "T101b fail-closed contract: git -C <REPO_ROOT> checkout -b x blocked even with valid python3" {
  # Integration complement: REPO_ROOT-targeted git -C must be forbidden.
  ( cd "$TMP_REPO" && git init -q -b main )
  ( cd "$TMP_REPO" && git config user.email t@t && git config user.name t )
  ( cd "$TMP_REPO" && git commit -q --allow-empty -m init )
  CLAUDE_WORKTREE_PATH="" _assert_forbidden "git -C $TMP_REPO checkout -b x"
}

# ---------------------------------------------------------------------------
# H2 — command-substitution bypass (T102-T105)
# ---------------------------------------------------------------------------

@test "T102 forbidden: cd \$(pwd) && git checkout -b evil (command-sub in cd target)" {
  _assert_forbidden 'cd $(pwd) && git checkout -b evil'
}

@test "T103 forbidden: git -C \$(pwd) checkout -b evil (command-sub in git -C target)" {
  _assert_forbidden 'git -C $(pwd) checkout -b evil'
}

@test "T104 forbidden: cd \`pwd\` && git checkout -b evil (backtick in cd target)" {
  _assert_forbidden 'cd `pwd` && git checkout -b evil'
}

@test "T105 allowed: git -C \"\$WORKTREE\" checkout foo (plain var still allowed after H2 fix)" {
  _assert_allowed 'git -C "$WORKTREE" checkout foo'
}

# ---------------------------------------------------------------------------
# M1 — multiple -C flags (T106-T108)
# ---------------------------------------------------------------------------

@test "T106 forbidden: git -C /nonexistent1 -C /nonexistent2 checkout foo (multi -C)" {
  _assert_forbidden 'git -C /nonexistent1 -C /nonexistent2 checkout foo'
}

@test "T107 forbidden: git -C \"\$WORKTREE\" -C ../../.. checkout -b evil (multi -C escape)" {
  _assert_forbidden 'git -C "$WORKTREE" -C ../../.. checkout -b evil'
}

@test "T108 allowed: git -C <registered-wt> checkout foo (single -C still allowed)" {
  ( cd "$TMP_REPO" && git init -q -b main )
  ( cd "$TMP_REPO" && git config user.email t@t && git config user.name t )
  ( cd "$TMP_REPO" && git commit -q --allow-empty -m init )
  local WT; WT="$(mktemp -d)/wt"
  ( cd "$TMP_REPO" && git worktree add -q -b feat/m1 "$WT" )
  CLAUDE_WORKTREE_PATH="$WT" _assert_allowed "git -C $WT checkout foo"
  rm -rf "$(dirname "$WT")"
}

# ---------------------------------------------------------------------------
# M2 — single-quoted path dequote (T109-T110)
# ---------------------------------------------------------------------------

@test "T109 allowed: git -C '<registered-wt>' checkout foo (single-quoted registered path)" {
  ( cd "$TMP_REPO" && git init -q -b main )
  ( cd "$TMP_REPO" && git config user.email t@t && git config user.name t )
  ( cd "$TMP_REPO" && git commit -q --allow-empty -m init )
  local WT; WT="$(mktemp -d)/wt"
  ( cd "$TMP_REPO" && git worktree add -q -b feat/m2 "$WT" )
  CLAUDE_WORKTREE_PATH="$WT" _assert_allowed "git -C '$WT' checkout foo"
  rm -rf "$(dirname "$WT")"
}

@test "T110 forbidden: git -C '<REPO_ROOT>' checkout -b x (single-quoted REPO_ROOT blocked)" {
  ( cd "$TMP_REPO" && git init -q -b main )
  ( cd "$TMP_REPO" && git config user.email t@t && git config user.name t )
  ( cd "$TMP_REPO" && git commit -q --allow-empty -m init )
  CLAUDE_WORKTREE_PATH="" _assert_forbidden "git -C '$TMP_REPO' checkout -b x"
}

# ---------------------------------------------------------------------------
# TAB-C — tab-separated -C must be blocked (T111-T112)
# The literal-space glob guard `*" -C "*` missed tab-separated forms, causing
# fail-OPEN. These tests verify the fix catches all [[:space:]] variants.
# ---------------------------------------------------------------------------

@test "T111 forbidden: git<TAB>-C<TAB>/tmp checkout -b evil (tab-separated -C, single)" {
  _assert_forbidden $'git\t-C\t/tmp checkout -b evil'
}

@test "T112 forbidden: git -C \"\$WORKTREE\"<TAB>-C<TAB>../../.. checkout -b x (tab multi-C escape)" {
  _assert_forbidden $'git -C "$WORKTREE"\t-C\t../../.. checkout -b x'
}

# ---------------------------------------------------------------------------
# Anomaly #6 fix — pathspec-form checkout and git-restore carve-outs (T113-T124)
# git checkout -- <pathspec> and git checkout <ref> -- <pathspec> restore files
# without moving HEAD; they must NOT be blocked.
# git restore <pathspec> (and its --source/--staged/--worktree variants) also
# do not move HEAD and must NOT be blocked.
# Branch-switching forms (no -- separator) must still be BLOCKED.
# ---------------------------------------------------------------------------

@test "T113 allowed: git checkout -- foo.sh (pathspec restore, no HEAD move)" {
  _assert_allowed 'git checkout -- foo.sh'
}

@test "T114 allowed: git checkout -- src/bar.py hooks/x.sh (multi-file pathspec)" {
  _assert_allowed 'git checkout -- src/bar.py hooks/x.sh'
}

@test "T115 allowed: git checkout HEAD -- foo.sh (ref + pathspec)" {
  _assert_allowed 'git checkout HEAD -- foo.sh'
}

@test "T116 allowed: git checkout origin/main -- hooks/main-branch-guard.sh (remote ref + pathspec)" {
  _assert_allowed 'git checkout origin/main -- hooks/main-branch-guard.sh'
}

@test "T117 allowed: git checkout abc123 -- src/app.ts (SHA ref + pathspec)" {
  _assert_allowed 'git checkout abc123 -- src/app.ts'
}

@test "T118 allowed: git restore foo.sh (basic restore)" {
  _assert_allowed 'git restore foo.sh'
}

@test "T119 allowed: git restore --source HEAD hooks/main-branch-guard.sh (restore with --source)" {
  _assert_allowed 'git restore --source HEAD hooks/main-branch-guard.sh'
}

@test "T120 allowed: git restore --staged foo.sh (restore from index)" {
  _assert_allowed 'git restore --staged foo.sh'
}

@test "T121 allowed: git restore --worktree foo.sh (restore worktree)" {
  _assert_allowed 'git restore --worktree foo.sh'
}

@test "T122 allowed: git restore --source HEAD --staged --worktree foo.sh (all flags)" {
  _assert_allowed 'git restore --source HEAD --staged --worktree foo.sh'
}

@test "T123 forbidden: git checkout foo (branch switch, no -- separator, still blocked)" {
  _assert_forbidden 'git checkout foo'
}

@test "T124 forbidden: git checkout -b newbranch (branch create, still blocked)" {
  _assert_forbidden 'git checkout -b newbranch'
}

# ---------------------------------------------------------------------------
# R2 fixes — -b/-B/--orphan bypass and trailing-dash-dash tightening (T125-T132)
# Finding #1 (HIGH): -b/--orphan with -- separator was wrongly allowed as pathspec.
# Finding #2 (SECURITY MEDIUM): trailing -- with no pathspec was wrongly allowed.
# ---------------------------------------------------------------------------

# Finding #1 — -b/-B/--orphan must be blocked even when -- separator is present.
@test "T125 forbidden: git checkout -b evil -- foo.sh (-b + pathspec separator)" {
  _assert_forbidden 'git checkout -b evil -- foo.sh'
}

@test "T126 forbidden: git checkout -B evil -- foo.sh (-B force-create + pathspec separator)" {
  _assert_forbidden 'git checkout -B evil -- foo.sh'
}

@test "T127 forbidden: git checkout --orphan evil -- foo.sh (--orphan + pathspec separator)" {
  _assert_forbidden 'git checkout --orphan evil -- foo.sh'
}

# Finding #2 — trailing -- with no pathspec must be blocked.
@test "T128 forbidden: git checkout main -- (trailing -- no pathspec)" {
  _assert_forbidden 'git checkout main --'
}

# Regression guards — pathspec forms that must still be allowed.
@test "T129 allowed: git checkout main -- . (trailing -- with pathspec dot)" {
  _assert_allowed 'git checkout main -- .'
}

@test "T130 allowed: git checkout -- . (bare -- with dot pathspec)" {
  _assert_allowed 'git checkout -- .'
}

# DOC pin: git restore forms are already allowed by the forbidden regex not
# matching 'restore' — these tests guard against future regex changes breaking
# the restore carve-out.
@test "T131 allowed: git restore foo.sh (restore not caught by forbidden regex)" {
  _assert_allowed 'git restore foo.sh'
}

@test "T132 allowed: git restore --staged foo.sh (restore --staged not caught by forbidden regex)" {
  _assert_allowed 'git restore --staged foo.sh'
}
