#!/usr/bin/env bats
# Conformance suite — local backend driver.

setup() {
  export HOME="$(mktemp -d)"
  unset CLAUDE_SESSION_STORE_BACKEND
  unset _SESSION_STORE_RESOLVED_BACKEND
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  source "$REPO_ROOT/hooks/_lib/session-store.sh"
  source "$BATS_TEST_DIRNAME/_conformance_cases.bash"
}

teardown() { rm -rf "$HOME"; }

@test "conformance/local: round-trip" { assert_round_trip; }
@test "conformance/local: get miss → exit 1" { assert_get_miss_exit_1; }
@test "conformance/local: delete then get → miss" { assert_delete_then_get_miss; }
@test "conformance/local: list includes hash" { assert_list_includes_hash; }
@test "conformance/local: list_subkeys emits headers" { assert_list_subkeys_emits_headers; }
@test "conformance/local: put dash reads stdin" { assert_put_dash_reads_stdin; }
@test "conformance/local: section headers survive round-trip" { assert_section_headers_survive_round_trip; }
@test "conformance/local: empty blob round-trip" { assert_empty_blob_round_trip; }
