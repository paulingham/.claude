#!/usr/bin/env bats
# Conformance suite — S3 backend driver. Uses on-disk aws shim.

setup() {
  BATS_FILE_TMPDIR="$(mktemp -d -t sessionstore.XXXXXX)"
  export BIN_DIR="$BATS_FILE_TMPDIR/bin"
  export HOME="$BATS_FILE_TMPDIR/home"; mkdir -p "$HOME"
  export CLAUDE_SESSION_STORE_BACKEND="s3"
  export CLAUDE_SESSION_STORE_BUCKET="conf-bucket"
  export CLAUDE_SESSION_STORE_PREFIX="sessions/"
  export AWS_LOG="$BATS_FILE_TMPDIR/aws-cnf.log"; : > "$AWS_LOG"
  export AWS_FAKE_STORE="$BATS_FILE_TMPDIR/aws-cnf-store"; mkdir -p "$AWS_FAKE_STORE"
  unset _SESSION_STORE_RESOLVED_BACKEND
  source "$BATS_TEST_DIRNAME/_cli_shims.bash"
  install_aws_shim
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  source "$REPO_ROOT/hooks/_lib/session-store.sh"
  source "$BATS_TEST_DIRNAME/_conformance_cases.bash"
}

teardown() { rm -rf "$BATS_FILE_TMPDIR"; }

@test "conformance/s3: round-trip" { assert_round_trip; }
@test "conformance/s3: get miss → exit 1" { assert_get_miss_exit_1; }
@test "conformance/s3: delete then get → miss" { assert_delete_then_get_miss; }
@test "conformance/s3: list includes hash" { assert_list_includes_hash; }
@test "conformance/s3: list_subkeys emits headers" { assert_list_subkeys_emits_headers; }
@test "conformance/s3: put dash reads stdin" { assert_put_dash_reads_stdin; }
@test "conformance/s3: section headers survive round-trip" { assert_section_headers_survive_round_trip; }
@test "conformance/s3: empty blob round-trip" { assert_empty_blob_round_trip; }

@test "conformance/s3: traversal in hash rejected" { assert_traversal_in_hash_rejected; }
@test "conformance/s3: traversal in subkey rejected" { assert_traversal_in_subkey_rejected; }
@test "conformance/s3: slash in hash rejected" { assert_slash_in_hash_rejected; }
@test "conformance/s3: leading dot in hash rejected" { assert_leading_dot_in_hash_rejected; }
@test "conformance/s3: empty hash rejected" { assert_empty_hash_rejected; }
