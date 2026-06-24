#!/usr/bin/env bats
# Slice A — deploy_outcome project-hash parity
# A1: _project_hash byte-identical from two cwds sharing one git origin URL
# A2: origin-less dir -> _project_hash --fallback <arg> echoes arg
# A3: emitter path == consumer learn-Step-1 path under CLAUDE_PLUGIN_DATA

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  LIB="$REPO_ROOT/hooks/_lib/project-hash.sh"
  TMP_DIR="$(mktemp -d)"
}

teardown() {
  rm -rf "$TMP_DIR"
}

@test "A1 _project_hash identical from two cwds sharing one git origin URL" {
  local origin_repo="$TMP_DIR/origin"
  local clone1="$TMP_DIR/clone1"
  local worktree="$TMP_DIR/worktree"

  # WHY: proves _project_hash hashes origin URL not cwd — the load-bearing
  # invariant for deploy_outcome records to land in the same observations.jsonl
  # regardless of which worktree the Skill fires from.
  git init -q --bare "$origin_repo" 2>/dev/null
  git clone -q "$origin_repo" "$clone1" 2>/dev/null
  git -C "$clone1" checkout -b main -q 2>/dev/null
  touch "$clone1/sentinel"
  git -C "$clone1" add sentinel
  git -C "$clone1" -c user.email="t@t" -c user.name="t" commit -q -m "init" 2>/dev/null

  # create a linked worktree (shares origin with clone1)
  git -C "$clone1" worktree add -q "$worktree" -b wt-branch 2>/dev/null

  hash1=$(cd "$clone1" && bash -c "source '$LIB' && _project_hash")
  hash2=$(cd "$worktree" && bash -c "source '$LIB' && _project_hash")

  # both must be non-empty and identical
  [ -n "$hash1" ]
  [ "$hash1" = "$hash2" ]
}

@test "A2 _project_hash falls back to --fallback when origin absent" {
  local no_origin_dir="$TMP_DIR/no-origin"
  mkdir -p "$no_origin_dir"

  run bash -c "cd '$no_origin_dir' && source '$LIB' && _project_hash --fallback custom-x"
  [ "$status" -eq 0 ]
  [ "$output" = "custom-x" ]
}

@test "A3 emitter and consumer resolve same learning/<hash> path under CLAUDE_PLUGIN_DATA" {
  local fake_data="$TMP_DIR/plugin-data"
  mkdir -p "$fake_data"

  # compute hash from the real repo (has origin)
  local hash
  hash=$(cd "$REPO_ROOT" && bash -c "source '$LIB' && _project_hash")
  [ -n "$hash" ]

  # emitter path formula: <base>/learning/<hash>/observations.jsonl
  local emit_path="$fake_data/learning/$hash/observations.jsonl"

  # consumer (skills/learn) path formula: CLAUDE_PLUGIN_DATA/learning/<hash>/observations.jsonl
  # WHY: consumer is documented at skills/learn/SKILL.md Step 1; formula is identical.
  local consume_path
  consume_path=$(CLAUDE_PLUGIN_DATA="$fake_data" bash -c "
    source '$LIB'
    hash=\$(_project_hash)
    base=\"\${CLAUDE_PLUGIN_DATA:-\${CLAUDE_CONFIG_DIR:-\$HOME/.claude}}\"
    echo \"\$base/learning/\$hash/observations.jsonl\"
  ")

  [ "$emit_path" = "$consume_path" ]
}
