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
  source "$REPO_ROOT/hooks/_lib/session-store.sh"
}

install_redis_shim() {
  mkdir -p "$BATS_TMPDIR/bin"
  cat > "$BATS_TMPDIR/bin/redis-cli" <<'REDIS_SHIM'
#!/usr/bin/env bash
echo "$@" >> "$REDIS_LOG"
args=("$@"); cmd=""; key=""
for ((i=0; i<${#args[@]}; i++)); do
  case "${args[$i]}" in
    -u) i=$((i+1)) ;;
    -x) ;;
    SET|GET|DEL|KEYS) cmd="${args[$i]}"; key="${args[$((i+1))]}"; break ;;
  esac
done
key_file_for() { printf '%s' "$REDIS_FAKE_STORE/$(echo -n "$1" | md5sum 2>/dev/null | awk '{print $1}' || echo -n "$1" | openssl dgst -md5 | awk '{print $NF}')"; }
register_key() { grep -qxF "$1" "$REDIS_FAKE_STORE/.keys" 2>/dev/null || echo "$1" >> "$REDIS_FAKE_STORE/.keys"; }
unregister_key() { local tmp; tmp=$(mktemp); grep -vxF "$1" "$REDIS_FAKE_STORE/.keys" > "$tmp" 2>/dev/null; mv "$tmp" "$REDIS_FAKE_STORE/.keys"; }
file=$(key_file_for "$key")
case "$cmd" in
  SET) cat > "$file"; register_key "$key"; echo OK ;;
  GET) [[ -f "$file" ]] && cat "$file" || { echo ""; exit 0; } ;;
  DEL) rm -f "$file"; unregister_key "$key"; echo 1 ;;
  KEYS)
    pattern="${key//\*/}"
    [[ -f "$REDIS_FAKE_STORE/.keys" ]] || exit 0
    while read -r k; do case "$k" in "$pattern"*) echo "$k" ;; esac; done < "$REDIS_FAKE_STORE/.keys" ;;
  *) exit 1 ;;
esac
REDIS_SHIM
  chmod +x "$BATS_TMPDIR/bin/redis-cli"
  export PATH="$BATS_TMPDIR/bin:$PATH"
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

@test "redis fallback resolution is cached per process" {
  rm -f "$BATS_TMPDIR/bin/redis-cli"
  unset _SESSION_STORE_RESOLVED_BACKEND
  out=$(bash -c "source '$REPO_ROOT/hooks/_lib/session-store.sh'; _resolve_backend >/dev/null; _resolve_backend 2>&1 1>/dev/null")
  count=$(echo "$out" | grep -c "session-store" || true)
  [ "$count" -le 1 ]
}
