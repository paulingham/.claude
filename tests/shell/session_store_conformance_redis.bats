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
  source "$BATS_TEST_DIRNAME/_cli_shims.bash"
  source "$REPO_ROOT/hooks/_lib/session-store.sh"
  source "$BATS_TEST_DIRNAME/_conformance_cases.bash"
}

teardown() { rm -rf "$HOME"; rm -rf "$REDIS_FAKE_STORE"; rm -f "$BATS_TMPDIR/bin/redis-cli"; }

@test "conformance/redis: round-trip" { assert_round_trip; }
@test "conformance/redis: get miss → exit 1" { assert_get_miss_exit_1; }
@test "conformance/redis: delete then get → miss" { assert_delete_then_get_miss; }
@test "conformance/redis: list includes hash" { assert_list_includes_hash; }
@test "conformance/redis: list_subkeys emits headers" { assert_list_subkeys_emits_headers; }
@test "conformance/redis: put dash reads stdin" { assert_put_dash_reads_stdin; }
@test "conformance/redis: section headers survive round-trip" { assert_section_headers_survive_round_trip; }
@test "conformance/redis: empty blob round-trip" { assert_empty_blob_round_trip; }
