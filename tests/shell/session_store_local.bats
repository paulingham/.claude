#!/usr/bin/env bats
# Local adapter contract tests (Slice 1).

setup() {
  BATS_FILE_TMPDIR="$(mktemp -d -t sessionstore.XXXXXX)"
  TEST_HOME="$BATS_FILE_TMPDIR/home"; mkdir -p "$TEST_HOME"
  export HOME="$TEST_HOME"
  export PROJECT_HASH="abc123"
  export SESSION_ID="notes"
  unset CLAUDE_SESSION_STORE_BACKEND
  unset _SESSION_STORE_RESOLVED_BACKEND
  STORE_DIR="$HOME/.claude/session-memory/$PROJECT_HASH"
  mkdir -p "$STORE_DIR"
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  source "$REPO_ROOT/hooks/_lib/session-store.sh"
}

teardown() {
  rm -rf "$BATS_FILE_TMPDIR"
}

@test "AC-1.2: put writes blob to backend, cmp returns 0" {
  local payload="$BATS_FILE_TMPDIR/payload.md"
  printf 'hello world\n' > "$payload"
  run session_store_put "$PROJECT_HASH" "$SESSION_ID" "$payload"
  [ "$status" -eq 0 ]
  cmp "$payload" "$STORE_DIR/$SESSION_ID.md"
}

@test "AC-1.3: get echoes blob to stdout, exit 0 on hit" {
  printf 'cycle-2 blob\n' > "$STORE_DIR/$SESSION_ID.md"
  run session_store_get "$PROJECT_HASH" "$SESSION_ID"
  [ "$status" -eq 0 ]
  [ "$output" = "cycle-2 blob" ]
}

@test "AC-1.4: get exit 1 + empty stdout + no stderr on missing file" {
  run session_store_get "$PROJECT_HASH" "$SESSION_ID"
  [ "$status" -eq 1 ]
  [ -z "$output" ]
}

@test "AC-1.5: get exit 1 + empty stdout + no stderr on missing project-hash dir" {
  rm -rf "$STORE_DIR"
  run session_store_get "missing-hash" "$SESSION_ID"
  [ "$status" -eq 1 ]
  [ -z "$output" ]
}

@test "AC-1.6: list echoes one project-hash per line, sorted ascending" {
  mkdir -p "$HOME/.claude/session-memory/zzz999"
  mkdir -p "$HOME/.claude/session-memory/aaa000"
  run session_store_list
  [ "$status" -eq 0 ]
  expected="aaa000
abc123
zzz999"
  [ "$output" = "$expected" ]
}

@test "AC-1.7: list_subkeys echoes one section header per line, no leading hash" {
  printf '# Session: Untitled\n_d_\n# Active Work\n_e_\n' > "$STORE_DIR/$SESSION_ID.md"
  run session_store_list_subkeys "$PROJECT_HASH" "$SESSION_ID"
  [ "$status" -eq 0 ]
  expected="Session: Untitled
Active Work"
  [ "$output" = "$expected" ]
}

@test "delete removes blob, returns 0 on absent or present" {
  printf 'doomed\n' > "$STORE_DIR/$SESSION_ID.md"
  run session_store_delete "$PROJECT_HASH" "$SESSION_ID"
  [ "$status" -eq 0 ]
  [ ! -f "$STORE_DIR/$SESSION_ID.md" ]
  run session_store_delete "$PROJECT_HASH" "$SESSION_ID"
  [ "$status" -eq 0 ]
}

@test "put reads from stdin when blob_path is dash" {
  run bash -c "source '$REPO_ROOT/hooks/_lib/session-store.sh' && printf 'piped data\n' | session_store_put '$PROJECT_HASH' '$SESSION_ID' -"
  [ "$status" -eq 0 ]
  [ "$(cat "$STORE_DIR/$SESSION_ID.md")" = "piped data" ]
}

@test "LOW/A05: _local_put creates parent dir with mode 0700" {
  local fresh_hash="freshdir$$"
  rm -rf "$HOME/.claude/session-memory/$fresh_hash"
  printf 'data' | session_store_put "$fresh_hash" "$SESSION_ID" -
  local mode
  mode=$(stat -f '%Lp' "$HOME/.claude/session-memory/$fresh_hash" 2>/dev/null \
       || stat -c '%a' "$HOME/.claude/session-memory/$fresh_hash" 2>/dev/null)
  [ "$mode" = "700" ]
}
