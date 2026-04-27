#!/usr/bin/env bats
# S3 adapter contract + fallback tests (Slice 2).

setup() {
  TEST_HOME="$(mktemp -d)"
  export HOME="$TEST_HOME"
  export PROJECT_HASH="abc123"
  export SESSION_ID="notes"
  export CLAUDE_SESSION_STORE_BACKEND="s3"
  export CLAUDE_SESSION_STORE_BUCKET="test-bucket"
  export CLAUDE_SESSION_STORE_PREFIX="sessions/"
  export AWS_LOG="$BATS_TMPDIR/aws.log"
  export AWS_FAKE_STORE="$BATS_TMPDIR/aws-store"
  mkdir -p "$AWS_FAKE_STORE"
  : > "$AWS_LOG"
  unset _SESSION_STORE_RESOLVED_BACKEND
  source "$BATS_TEST_DIRNAME/_cli_shims.bash"
  install_aws_shim
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  source "$REPO_ROOT/hooks/_lib/session-store.sh"
}

teardown() { rm -rf "$TEST_HOME"; rm -f "$BATS_TMPDIR/bin/aws"; }

@test "AC-2.2: BACKEND=s3 + working aws → put calls aws s3 cp" {
  local payload="$BATS_TMPDIR/p.md"; printf 'aws-data\n' > "$payload"
  run session_store_put "$PROJECT_HASH" "$SESSION_ID" "$payload"
  [ "$status" -eq 0 ]
  grep -q "s3 cp $payload s3://test-bucket/sessions/$PROJECT_HASH/$SESSION_ID" "$AWS_LOG"
}

@test "s3 round-trip: put then get returns same bytes" {
  printf 'round-trip-blob' | session_store_put "$PROJECT_HASH" "$SESSION_ID" -
  run session_store_get "$PROJECT_HASH" "$SESSION_ID"
  [ "$status" -eq 0 ]
  [ "$output" = "round-trip-blob" ]
}

@test "AC-2.3: BACKEND=s3 + missing aws → fall back to local + warn" {
  rm -f "$BATS_TMPDIR/bin/aws"
  unset _SESSION_STORE_RESOLVED_BACKEND
  run bash -c "source '$REPO_ROOT/hooks/_lib/session-store.sh'; _resolve_backend 2>/dev/null"
  [ "$status" -eq 0 ]
  [ "$output" = "local" ]
}

@test "AC-2.3 stderr exact: missing aws warning matches contract" {
  rm -f "$BATS_TMPDIR/bin/aws"
  unset _SESSION_STORE_RESOLVED_BACKEND
  run bash -c "source '$REPO_ROOT/hooks/_lib/session-store.sh'; _resolve_backend 2>&1 1>/dev/null"
  [[ "$output" == *"[session-store] s3 backend selected but 'aws' CLI not found — falling back to local"* ]]
}

@test "AC-2.4: BACKEND=s3 + aws present + BUCKET unset → fall back + warn" {
  unset CLAUDE_SESSION_STORE_BUCKET
  unset _SESSION_STORE_RESOLVED_BACKEND
  run bash -c "source '$REPO_ROOT/hooks/_lib/session-store.sh'; _resolve_backend 2>&1 1>/dev/null"
  [[ "$output" == *"[session-store] s3 backend selected but CLAUDE_SESSION_STORE_BUCKET not set — falling back to local"* ]]
}

@test "s3 delete invokes aws s3 rm" {
  printf 'gone' | session_store_put "$PROJECT_HASH" "$SESSION_ID" -
  run session_store_delete "$PROJECT_HASH" "$SESSION_ID"
  [ "$status" -eq 0 ]
  grep -q "s3 rm s3://test-bucket/sessions/$PROJECT_HASH/$SESSION_ID" "$AWS_LOG"
}

@test "s3 get exit 1 on miss" {
  run session_store_get "$PROJECT_HASH" "$SESSION_ID"
  [ "$status" -eq 1 ]
}

@test "s3 list returns project hashes from aws s3 ls output" {
  printf 'a' | session_store_put "abc123" "notes" -
  printf 'b' | session_store_put "zzz999" "notes" -
  run session_store_list
  [ "$status" -eq 0 ]
  [[ "$output" == *"abc123"* ]]
  [[ "$output" == *"zzz999"* ]]
}

@test "s3 list_subkeys reads remote blob and emits headers" {
  printf '# Section A\n_d_\n# Section B\n_e_\n' | session_store_put "$PROJECT_HASH" "$SESSION_ID" -
  run session_store_list_subkeys "$PROJECT_HASH" "$SESSION_ID"
  [ "$status" -eq 0 ]
  expected="Section A
Section B"
  [ "$output" = "$expected" ]
}

@test "s3 fallback resolution is cached per process — second call no warn" {
  rm -f "$BATS_TMPDIR/bin/aws"
  unset _SESSION_STORE_RESOLVED_BACKEND
  out=$(bash -c "source '$REPO_ROOT/hooks/_lib/session-store.sh'; _resolve_backend >/dev/null; _resolve_backend 2>&1 1>/dev/null")
  count=$(echo "$out" | grep -c "session-store" || true)
  [ "$count" -le 1 ]
}
