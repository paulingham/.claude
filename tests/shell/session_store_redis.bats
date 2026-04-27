#!/usr/bin/env bats
# Redis adapter contract + fallback tests (Slice 3).

setup() {
  TEST_HOME="$(mktemp -d)"
  export HOME="$TEST_HOME"
  export PROJECT_HASH="abc123"
  export SESSION_ID="notes"
  export CLAUDE_SESSION_STORE_BACKEND="redis"
  export CLAUDE_SESSION_STORE_REDIS_URL="redis://x"
  export CLAUDE_SESSION_STORE_PREFIX="sessions/"
  export REDIS_LOG="$BATS_TMPDIR/redis.log"
  export REDIS_FAKE_STORE="$BATS_TMPDIR/redis-store"
  mkdir -p "$REDIS_FAKE_STORE"
  : > "$REDIS_LOG"
  unset _SESSION_STORE_RESOLVED_BACKEND
  install_redis_shim
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  source "$BATS_TEST_DIRNAME/_cli_shims.bash"
  source "$REPO_ROOT/hooks/_lib/session-store.sh"
}

teardown() { rm -rf "$TEST_HOME"; rm -f "$BATS_TMPDIR/bin/redis-cli"; }

@test "AC-3.2: BACKEND=redis + working redis-cli → put calls redis-cli SET" {
  printf 'redis-data' | session_store_put "$PROJECT_HASH" "$SESSION_ID" -
  grep -q "SET sessions/$PROJECT_HASH:$SESSION_ID" "$REDIS_LOG"
}

@test "redis round-trip: put then get returns same bytes" {
  printf 'rrt-blob' | session_store_put "$PROJECT_HASH" "$SESSION_ID" -
  run session_store_get "$PROJECT_HASH" "$SESSION_ID"
  [ "$status" -eq 0 ]
  [ "$output" = "rrt-blob" ]
}

@test "AC-3.3: BACKEND=redis + missing redis-cli → fall back" {
  rm -f "$BATS_TMPDIR/bin/redis-cli"
  unset _SESSION_STORE_RESOLVED_BACKEND
  run bash -c "source '$REPO_ROOT/hooks/_lib/session-store.sh'; _resolve_backend 2>/dev/null"
  [ "$status" -eq 0 ]
  [ "$output" = "local" ]
}

@test "AC-3.3 stderr exact: missing redis-cli warning matches contract" {
  rm -f "$BATS_TMPDIR/bin/redis-cli"
  unset _SESSION_STORE_RESOLVED_BACKEND
  run bash -c "source '$REPO_ROOT/hooks/_lib/session-store.sh'; _resolve_backend 2>&1 1>/dev/null"
  [[ "$output" == *"[session-store] redis backend selected but 'redis-cli' not found — falling back to local"* ]]
}

@test "AC-3.4: BACKEND=redis + redis-cli present + REDIS_URL unset → fall back + warn" {
  unset CLAUDE_SESSION_STORE_REDIS_URL
  unset _SESSION_STORE_RESOLVED_BACKEND
  run bash -c "source '$REPO_ROOT/hooks/_lib/session-store.sh'; _resolve_backend 2>&1 1>/dev/null"
  [[ "$output" == *"[session-store] redis backend selected but CLAUDE_SESSION_STORE_REDIS_URL not set — falling back to local"* ]]
}

@test "redis delete invokes redis-cli DEL" {
  printf 'gone' | session_store_put "$PROJECT_HASH" "$SESSION_ID" -
  run session_store_delete "$PROJECT_HASH" "$SESSION_ID"
  [ "$status" -eq 0 ]
  grep -q "DEL sessions/$PROJECT_HASH:$SESSION_ID" "$REDIS_LOG"
}

@test "redis get exit 1 on miss" {
  run session_store_get "$PROJECT_HASH" "$SESSION_ID"
  [ "$status" -eq 1 ]
}

@test "redis list returns project hashes via KEYS" {
  printf 'a' | session_store_put "abc123" "notes" -
  printf 'b' | session_store_put "zzz999" "notes" -
  run session_store_list
  [ "$status" -eq 0 ]
  [[ "$output" == *"abc123"* ]]
  [[ "$output" == *"zzz999"* ]]
}

@test "redis list_subkeys reads remote blob + emits headers" {
  printf '# Section A\n_d_\n# Section B\n_e_\n' | session_store_put "$PROJECT_HASH" "$SESSION_ID" -
  run session_store_list_subkeys "$PROJECT_HASH" "$SESSION_ID"
  [ "$status" -eq 0 ]
  expected="Section A
Section B"
  [ "$output" = "$expected" ]
}

@test "redis empty-blob round-trip: put empty then get returns exit 0 with empty stdout" {
  printf '' | session_store_put "$PROJECT_HASH" "$SESSION_ID" -
  run session_store_get "$PROJECT_HASH" "$SESSION_ID"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "redis fallback resolution is cached per process" {
  rm -f "$BATS_TMPDIR/bin/redis-cli"
  unset _SESSION_STORE_RESOLVED_BACKEND
  out=$(bash -c "source '$REPO_ROOT/hooks/_lib/session-store.sh'; _resolve_backend >/dev/null; _resolve_backend 2>&1 1>/dev/null")
  count=$(echo "$out" | grep -c "session-store" || true)
  [ "$count" -le 1 ]
}
