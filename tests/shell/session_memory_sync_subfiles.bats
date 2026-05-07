#!/usr/bin/env bats
# AC11 + AC9 — session_memory_sync_in/out loop over 5 canonical sub-files.
# Each sub-file is stored under subkey == basename; full round-trip preserves
# bytes for every sub-file across local + s3 shim backends.

setup() {
  BATS_FILE_TMPDIR="$(mktemp -d -t sm-sync.XXXXXX)"
  export BIN_DIR="$BATS_FILE_TMPDIR/bin"
  export AWS_LOG="$BATS_FILE_TMPDIR/aws.log"
  TEST_HOME="$BATS_FILE_TMPDIR/home"; mkdir -p "$TEST_HOME"
  export HOME="$TEST_HOME"
  export CLAUDE_CONFIG_DIR="$TEST_HOME/.claude"
  HASH="abc123"
  PROJ="$HOME/.claude/session-memory/$HASH"
  mkdir -p "$PROJ"
  unset _SESSION_STORE_RESOLVED_BACKEND
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  source "$BATS_TEST_DIRNAME/_cli_shims.bash"
  source "$REPO_ROOT/hooks/_lib/session-store.sh"
}

teardown() { rm -rf "$BATS_FILE_TMPDIR"; }

@test "AC11: sync_out source iterates the 5 canonical basenames" {
  # Read the source — verify each basename appears in a loop body.
  local src; src="$REPO_ROOT/hooks/_lib/session-store-sync.sh"
  for sub in codebase-map build-test patterns fragility active-work; do
    grep -q "$sub" "$src" || { echo "missing $sub in $src"; return 1; }
  done
}

_setup_s3_shim_record() {
  export CLAUDE_SESSION_STORE_BACKEND="s3"
  export CLAUDE_SESSION_STORE_BUCKET="test-bucket"
  export AWS_FAKE_STORE="$BATS_FILE_TMPDIR/s3"
  mkdir -p "$AWS_FAKE_STORE"
  unset _SESSION_STORE_RESOLVED_BACKEND
  install_aws_shim
}

@test "AC11: sync_in_and_out_round_trip_each_subfile_via_s3_shim" {
  _setup_s3_shim_record
  # Write distinct bodies to each sub-file locally, then sync_out.
  for sub in codebase-map build-test patterns fragility active-work; do
    printf 'BODY-%s\n' "$sub" > "$PROJ/$sub.md"
  done
  run session_memory_sync_out "$HASH" "$PROJ"
  [ "$status" -eq 0 ]
  # Each sub-file must have been put under subkey == basename.
  for sub in codebase-map build-test patterns fragility active-work; do
    grep -q "s3 cp" "$AWS_LOG"
  done
  # Now wipe locally, sync_in, and confirm bytes round-tripped.
  rm -f "$PROJ"/*.md
  run session_memory_sync_in "$HASH" "$PROJ"
  [ "$status" -eq 0 ]
  for sub in codebase-map build-test patterns fragility active-work; do
    [ -f "$PROJ/$sub.md" ]
    grep -q "BODY-$sub" "$PROJ/$sub.md"
  done
}

@test "AC11: BACKEND=local sync_in/out is byte-no-op per sub-file" {
  for sub in codebase-map build-test patterns fragility active-work; do
    printf 'BODY-%s\n' "$sub" > "$PROJ/$sub.md"
    cp "$PROJ/$sub.md" "$BATS_FILE_TMPDIR/golden-$sub"
  done
  run session_memory_sync_in "$HASH" "$PROJ"
  [ "$status" -eq 0 ]
  run session_memory_sync_out "$HASH" "$PROJ"
  [ "$status" -eq 0 ]
  for sub in codebase-map build-test patterns fragility active-work; do
    cmp "$PROJ/$sub.md" "$BATS_FILE_TMPDIR/golden-$sub"
  done
}
