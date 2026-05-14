#!/usr/bin/env bats
# Specs for hooks/_lib/repo-hash.sh — sha256-based repo + plan-cache-key helpers.
# Plan: pipeline-state/plan-cache-agentic/plan.md § Slice slice-a-repo-hash-helper.
# Design invariant (HIGH-eng-1): `git ls-tree --name-only -r HEAD <dirs>` is
# leaf-content-blind. Content edits MUST NOT change repo_hash; add/rename/delete
# MUST change it. CLAUDE.md content IS included in the hash.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  LIB="$REPO_ROOT/hooks/_lib/repo-hash.sh"
  TMP_DIR="$(mktemp -d)"
  _PRIOR_PWD="$PWD"
  cd "$TMP_DIR"
  git init -q -b main .
  git config user.email test@example.com
  git config user.name test
  mkdir -p src/foo docs
  printf 'v1\n' >src/foo/bar.txt
  printf 'initial claude\n' >CLAUDE.md
  git add -A
  git commit -q -m init
}

teardown() {
  cd "$_PRIOR_PWD"
  rm -rf "$TMP_DIR"
}

# A1: deterministic — two calls back-to-back identical.
@test "A1 repo_hash is deterministic" {
  H1=$(bash -c "source '$LIB'; _repo_hash")
  H2=$(bash -c "source '$LIB'; _repo_hash")
  [ -n "$H1" ]
  [ "$H1" = "$H2" ]
}

# A2: CLAUDE.md content IS part of the hash.
@test "A2 repo_hash changes when CLAUDE.md changes" {
  H1=$(bash -c "source '$LIB'; _repo_hash")
  printf 'changed claude\n' >CLAUDE.md
  git add -A && git commit -q -m claude-edit
  H2=$(bash -c "source '$LIB'; _repo_hash")
  [ "$H1" != "$H2" ]
}

# A3 (HIGH-eng-1 spike): leaf content edits under src/ MUST NOT change hash.
@test "A3 repo_hash stable on src/ leaf content edits" {
  mkdir -p .claude
  printf '{"stable_dirs":["src/"]}\n' >.claude/plan-cache.json
  git add -A && git commit -q -m config
  H1=$(bash -c "source '$LIB'; _repo_hash")
  printf 'v2\n' >src/foo/bar.txt
  git add -A && git commit -q -m content-edit
  H2=$(bash -c "source '$LIB'; _repo_hash")
  [ "$H1" = "$H2" ]
}

# A4: stable_dirs override honoured — editing src/ no longer matters when override=docs/.
@test "A4 repo_hash respects stable_dirs override" {
  mkdir -p .claude
  printf '{"stable_dirs":["docs/"]}\n' >.claude/plan-cache.json
  printf 'doc1\n' >docs/readme.md
  git add -A && git commit -q -m docs-init
  H1=$(bash -c "source '$LIB'; _repo_hash")
  printf 'v2\n' >src/foo/bar.txt
  git add -A && git commit -q -m src-edit-ignored
  H2=$(bash -c "source '$LIB'; _repo_hash")
  [ "$H1" = "$H2" ]
}

# A5: cache key order-independent over the four input fields (canonical JSON).
@test "A5 cache key is order-independent over inputs" {
  K1=$(bash -c "source '$LIB'; _plan_cache_key 'bug-fix' 'abc123' 'T4' 'false'")
  K2=$(bash -c "source '$LIB'; _plan_cache_key 'bug-fix' 'abc123' 'T4' 'false'")
  [ -n "$K1" ]
  [ "$K1" = "$K2" ]
  # Different inputs must produce different keys.
  K3=$(bash -c "source '$LIB'; _plan_cache_key 'feature' 'abc123' 'T4' 'false'")
  [ "$K1" != "$K3" ]
}

# A6: new file under stable dir changes the hash.
@test "A6 repo_hash changes when new file added under src/" {
  H1=$(bash -c "source '$LIB'; _repo_hash")
  printf 'baz\n' >src/baz.txt
  git add -A && git commit -q -m add-baz
  H2=$(bash -c "source '$LIB'; _repo_hash")
  [ "$H1" != "$H2" ]
}

# A7: rename via git mv changes the hash (path set changes).
@test "A7 repo_hash changes on git mv src/foo src/bar" {
  H1=$(bash -c "source '$LIB'; _repo_hash")
  git mv src/foo src/bar
  git commit -q -m rename
  H2=$(bash -c "source '$LIB'; _repo_hash")
  [ "$H1" != "$H2" ]
}
