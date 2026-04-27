#!/usr/bin/env bats
# Sync helpers: sync_in / sync_out (Slice 4).

setup() {
  TEST_HOME="$(mktemp -d)"
  export HOME="$TEST_HOME"
  export PROJECT_HASH="abc123"
  STORE_DIR="$HOME/.claude/session-memory/$PROJECT_HASH"
  NOTES="$STORE_DIR/notes.md"
  mkdir -p "$STORE_DIR"
  unset _SESSION_STORE_RESOLVED_BACKEND
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  source "$BATS_TEST_DIRNAME/_cli_shims.bash"
  source "$REPO_ROOT/hooks/_lib/session-store.sh"
}

teardown() { rm -rf "$TEST_HOME"; }

@test "AC-4.1: BACKEND=local sync_in is byte-no-op" {
  printf 'pre-state\n' > "$NOTES"
  cp "$NOTES" "$BATS_TMPDIR/golden"
  run session_memory_sync_in "$PROJECT_HASH" "$NOTES"
  [ "$status" -eq 0 ]
  cmp "$NOTES" "$BATS_TMPDIR/golden"
}

@test "AC-4.1: BACKEND=local sync_out is byte-no-op" {
  printf 'post-state\n' > "$NOTES"
  cp "$NOTES" "$BATS_TMPDIR/golden"
  run session_memory_sync_out "$PROJECT_HASH" "$NOTES"
  [ "$status" -eq 0 ]
  cmp "$NOTES" "$BATS_TMPDIR/golden"
}

@test "AC-4.2: sync_in on missing remote + existing local file → leaves local untouched" {
  setup_s3_shim_404
  printf 'preserved\n' > "$NOTES"
  cp "$NOTES" "$BATS_TMPDIR/golden"
  run session_memory_sync_in "$PROJECT_HASH" "$NOTES"
  [ "$status" -eq 0 ]
  cmp "$NOTES" "$BATS_TMPDIR/golden"
}

@test "AC-4.3: sync_in on missing remote + missing local → writes template stamp" {
  setup_s3_shim_404
  rm -f "$NOTES"
  run session_memory_sync_in "$PROJECT_HASH" "$NOTES"
  [ "$status" -eq 0 ]
  [ -f "$NOTES" ]
  grep -q "# Session: Untitled" "$NOTES"
  grep -q "# Active Work" "$NOTES"
  grep -q "# Codebase Map" "$NOTES"
}

@test "AC-4.4: sync_out PUT failure → JSONL line + stderr warning + exit 0" {
  setup_s3_shim_fail
  export CLAUDE_SESSION_ID="test-session"
  printf 'doomed\n' > "$NOTES"
  run session_memory_sync_out "$PROJECT_HASH" "$NOTES"
  [ "$status" -eq 0 ]
  [[ "${output}${stderr}" == *"sync_out put failed"* ]] || [[ "$output" == *"put failed"* ]]
  jsonl_path="$HOME/.claude/metrics/test-session/session-store-mirror.jsonl"
  [ -s "$jsonl_path" ]
}

@test "sync_in writes blob from successful remote GET" {
  setup_s3_shim_with_blob "remote-content\n"
  rm -f "$NOTES"
  run session_memory_sync_in "$PROJECT_HASH" "$NOTES"
  [ "$status" -eq 0 ]
  [ -f "$NOTES" ]
  grep -q "remote-content" "$NOTES"
}

@test "sync_out writes file blob to remote backend" {
  setup_s3_shim_record
  printf 'mirror-this\n' > "$NOTES"
  run session_memory_sync_out "$PROJECT_HASH" "$NOTES"
  [ "$status" -eq 0 ]
  grep -q "s3 cp $NOTES" "$AWS_LOG"
}

@test "sync_out missing local file is a no-op (exit 0)" {
  setup_s3_shim_record
  rm -f "$NOTES"
  run session_memory_sync_out "$PROJECT_HASH" "$NOTES"
  [ "$status" -eq 0 ]
}

@test "MEDIUM-3: sync_in empty-blob remote hit + missing local → writes empty file (no template stamp)" {
  setup_s3_shim_with_blob ""
  rm -f "$NOTES"
  run session_memory_sync_in "$PROJECT_HASH" "$NOTES"
  [ "$status" -eq 0 ]
  [ -f "$NOTES" ]
  ! grep -q "# Session: Untitled" "$NOTES"
}

@test "MEDIUM-3: sync_in empty-blob remote hit + existing local → overwrites with empty (hit wins)" {
  setup_s3_shim_with_blob ""
  printf 'pre-existing
' > "$NOTES"
  run session_memory_sync_in "$PROJECT_HASH" "$NOTES"
  [ "$status" -eq 0 ]
  [ -f "$NOTES" ]
  ! grep -q "pre-existing" "$NOTES"
}

setup_s3_shim_fail() {
  setup_s3_shim_404
}

setup_s3_shim_with_blob() {
  export CLAUDE_SESSION_STORE_BACKEND="s3"
  export CLAUDE_SESSION_STORE_BUCKET="test-bucket"
  export AWS_LOG="$BATS_TMPDIR/aws.log"; : > "$AWS_LOG"
  export AWS_BLOB="$1"
  unset _SESSION_STORE_RESOLVED_BACKEND
  mkdir -p "$BATS_TMPDIR/bin"
  cat > "$BATS_TMPDIR/bin/aws" <<'SHIM'
#!/usr/bin/env bash
echo "$@" >> "$AWS_LOG"
case "$1 $2" in
  "s3 cp")
    if [[ "$3" == s3://* ]]; then printf '%b' "$AWS_BLOB"; exit 0; fi
    cat > /dev/null; exit 0 ;;
esac
exit 1
SHIM
  chmod +x "$BATS_TMPDIR/bin/aws"
  export PATH="$BATS_TMPDIR/bin:$PATH"
}

setup_s3_shim_record() {
  export CLAUDE_SESSION_STORE_BACKEND="s3"
  export CLAUDE_SESSION_STORE_BUCKET="test-bucket"
  export AWS_LOG="$BATS_TMPDIR/aws.log"; : > "$AWS_LOG"
  unset _SESSION_STORE_RESOLVED_BACKEND
  mkdir -p "$BATS_TMPDIR/bin"
  cat > "$BATS_TMPDIR/bin/aws" <<'SHIM'
#!/usr/bin/env bash
echo "$@" >> "$AWS_LOG"
[[ "$1 $2" == "s3 cp" ]] && exit 0
exit 1
SHIM
  chmod +x "$BATS_TMPDIR/bin/aws"
  export PATH="$BATS_TMPDIR/bin:$PATH"
}

setup_s3_shim_404() {
  export CLAUDE_SESSION_STORE_BACKEND="s3"
  export CLAUDE_SESSION_STORE_BUCKET="test-bucket"
  unset _SESSION_STORE_RESOLVED_BACKEND
  install_aws_shim_404
}

setup_s3_shim_fail() { setup_s3_shim_404; }

setup_s3_shim_with_blob() {
  export CLAUDE_SESSION_STORE_BACKEND="s3"
  export CLAUDE_SESSION_STORE_BUCKET="test-bucket"
  unset _SESSION_STORE_RESOLVED_BACKEND
  install_aws_shim_with_blob "$1"
}

setup_s3_shim_record() {
  export CLAUDE_SESSION_STORE_BACKEND="s3"
  export CLAUDE_SESSION_STORE_BUCKET="test-bucket"
  unset _SESSION_STORE_RESOLVED_BACKEND
  install_aws_shim_record
}
