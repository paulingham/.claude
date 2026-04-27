#!/usr/bin/env bats
# Conformance suite — Redis backend driver. Uses on-disk redis-cli shim.

setup() {
  export HOME="$(mktemp -d)"
  export CLAUDE_SESSION_STORE_BACKEND="redis"
  export CLAUDE_SESSION_STORE_REDIS_URL="redis://x"
  export CLAUDE_SESSION_STORE_PREFIX="sessions/"
  export REDIS_LOG="$BATS_TMPDIR/redis-cnf.log"; : > "$REDIS_LOG"
  export REDIS_FAKE_STORE="$BATS_TMPDIR/redis-cnf-store"; rm -rf "$REDIS_FAKE_STORE"; mkdir -p "$REDIS_FAKE_STORE"
  unset _SESSION_STORE_RESOLVED_BACKEND
  install_redis_shim
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  source "$REPO_ROOT/hooks/_lib/session-store.sh"
  source "$BATS_TEST_DIRNAME/_conformance_cases.bash"
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

teardown() { rm -rf "$HOME"; rm -rf "$REDIS_FAKE_STORE"; rm -f "$BATS_TMPDIR/bin/redis-cli"; }

@test "conformance/redis: round-trip" { assert_round_trip; }
@test "conformance/redis: get miss → exit 1" { assert_get_miss_exit_1; }
@test "conformance/redis: delete then get → miss" { assert_delete_then_get_miss; }
@test "conformance/redis: list includes hash" { assert_list_includes_hash; }
@test "conformance/redis: list_subkeys emits headers" { assert_list_subkeys_emits_headers; }
@test "conformance/redis: put dash reads stdin" { assert_put_dash_reads_stdin; }
@test "conformance/redis: section headers survive round-trip" { assert_section_headers_survive_round_trip; }
