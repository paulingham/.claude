#!/usr/bin/env bats
# AC5/AC10/AC16 — session_memory_read_split helper.
# Prefers new layout, falls back to legacy notes.md, supports partial migration,
# emits a forensic JSONL line on each fallback.

setup() {
  BATS_FILE_TMPDIR="$(mktemp -d -t sm-readsplit.XXXXXX)"
  TEST_HOME="$BATS_FILE_TMPDIR/home"; mkdir -p "$TEST_HOME"
  export HOME="$TEST_HOME"
  export CLAUDE_CONFIG_DIR="$TEST_HOME/.claude"
  STORE_ROOT="$CLAUDE_CONFIG_DIR/session-memory"
  mkdir -p "$STORE_ROOT"
  HASH="abc123"
  PROJ="$STORE_ROOT/$HASH"
  mkdir -p "$PROJ"
  unset _SESSION_STORE_RESOLVED_BACKEND
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  source "$REPO_ROOT/hooks/_lib/session-store.sh"
  export CLAUDE_SESSION_ID="test-session"
}

teardown() { rm -rf "$BATS_FILE_TMPDIR"; }

_seed_full_legacy_notes() {
  cat > "$PROJ/notes.md" <<'EOF'
# Session: Hello
_Title_

# Active Work
in-flight ABC

# Codebase Map
src/index.ts entry

# Build & Test
npm test runs

# Critical Paths
auth.ts is fragile

# Patterns & Conventions
service objects everywhere

# Session Discoveries
mocked DB breaks

# Agent Effectiveness
sonnet-4-6 wins
EOF
}

_seed_subfile() {
  local sub="$1" body="$2"
  printf '# %s\n_desc_\n%s\n' "$sub" "$body" > "$PROJ/$sub.md"
}

@test "AC5: read_split prefers new layout when sub-file present" {
  _seed_subfile "patterns" "from-new-layout"
  run session_memory_read_split "$HASH" "patterns"
  [ "$status" -eq 0 ]
  [[ "$output" == *"from-new-layout"* ]]
}

@test "AC5: read_split falls back to legacy notes.md when sub-file missing" {
  _seed_full_legacy_notes
  run session_memory_read_split "$HASH" "patterns"
  [ "$status" -eq 0 ]
  [[ "$output" == *"service objects everywhere"* ]]
}

@test "AC5: read_split exits 1 when neither new nor legacy present" {
  run session_memory_read_split "$HASH" "patterns"
  [ "$status" -ne 0 ]
}

@test "AC5: read_split for fragility extracts Critical Paths section from legacy" {
  _seed_full_legacy_notes
  run session_memory_read_split "$HASH" "fragility"
  [ "$status" -eq 0 ]
  [[ "$output" == *"auth.ts is fragile"* ]]
}

@test "AC5: read_split for build-test extracts Build & Test section from legacy" {
  _seed_full_legacy_notes
  run session_memory_read_split "$HASH" "build-test"
  [ "$status" -eq 0 ]
  [[ "$output" == *"npm test runs"* ]]
}

@test "AC10: partial-migration reads new files for present subs and falls back for missing" {
  _seed_full_legacy_notes
  _seed_subfile "patterns" "NEW_PATTERNS_BODY"
  _seed_subfile "build-test" "NEW_BT_BODY"
  _seed_subfile "fragility" "NEW_FRAG_BODY"
  _seed_subfile "active-work" "NEW_AW_BODY"
  # codebase-map is missing — must fall back to legacy.
  run session_memory_read_split "$HASH" "patterns"
  [ "$status" -eq 0 ]; [[ "$output" == *"NEW_PATTERNS_BODY"* ]]
  run session_memory_read_split "$HASH" "codebase-map"
  [ "$status" -eq 0 ]
  [[ "$output" == *"src/index.ts entry"* ]]
}

@test "AC16: fallback writes forensic JSONL line" {
  _seed_full_legacy_notes
  run session_memory_read_split "$HASH" "patterns"
  [ "$status" -eq 0 ]
  jsonl="$HOME/.claude/metrics/test-session/session-store-mirror.jsonl"
  [ -s "$jsonl" ]
  grep -q "session-memory-read-fallback" "$jsonl"
  grep -q "$HASH"                        "$jsonl"
  grep -q "patterns"                     "$jsonl"
}

@test "AC16: new-layout hit does NOT write fallback JSONL line" {
  _seed_subfile "patterns" "from-new-layout"
  run session_memory_read_split "$HASH" "patterns"
  [ "$status" -eq 0 ]
  jsonl="$HOME/.claude/metrics/test-session/session-store-mirror.jsonl"
  if [[ -f "$jsonl" ]]; then
    ! grep -q "session-memory-read-fallback" "$jsonl"
  fi
}
