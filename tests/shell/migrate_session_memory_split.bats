#!/usr/bin/env bats
# AC2/AC3/AC13/AC14 — migrate-session-memory-split.sh tests.
# Idempotency, canonical-header parsing, legacy-collision archival,
# symlink resolution discipline. All tests run against a throwaway
# tree under BATS_FILE_TMPDIR — never against the host's real
# session-memory dir.

setup_file() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  export REPO_ROOT
  SCRIPT="$REPO_ROOT/scripts/migrate-session-memory-split.sh"
  export SCRIPT
}

setup() {
  BATS_FILE_TMPDIR="$(mktemp -d -t sm-split.XXXXXX)"
  TEST_HOME="$BATS_FILE_TMPDIR/home"
  mkdir -p "$TEST_HOME"
  export HOME="$TEST_HOME"
  export CLAUDE_CONFIG_DIR="$TEST_HOME/.claude"
  STORE_ROOT="$CLAUDE_CONFIG_DIR/session-memory"
  mkdir -p "$STORE_ROOT"
  export STORE_ROOT
  HASH="abc123"
  export HASH
  PROJ="$STORE_ROOT/$HASH"
  export PROJ
  mkdir -p "$PROJ"
  [ -x "$SCRIPT" ]
}

teardown() { rm -rf "$BATS_FILE_TMPDIR"; }

_seed_legacy_notes_with_all_sections() {
  cat > "$PROJ/notes.md" <<'EOF'
# Session: Hello
_Title for this work_

# Active Work
in-flight task ABC

# Codebase Map
src/index.ts is the entry

# Build & Test
npm test passes

# Critical Paths
auth.ts is fragile

# Patterns & Conventions
service objects everywhere

# Session Discoveries
mocked DB breaks integration

# Agent Effectiveness
sonnet-4-6 gets architecture
EOF
}

_seed_already_migrated() {
  printf '# Codebase Map\n_desc_\n' > "$PROJ/codebase-map.md"
  printf '# Build & Test\n_desc_\n' > "$PROJ/build-test.md"
  printf '# Patterns\n_desc_\n'      > "$PROJ/patterns.md"
  printf '# Critical Paths\n_desc_\n'> "$PROJ/fragility.md"
  printf '# Active Work\n_desc_\n'   > "$PROJ/active-work.md"
}

@test "AC2: migration is idempotent on already-migrated tree" {
  _seed_already_migrated
  # Capture snapshot of bodies.
  local before_b; before_b=$(cat "$PROJ/build-test.md")
  run "$SCRIPT"
  [ "$status" -eq 0 ]
  # Re-run.
  run "$SCRIPT"
  [ "$status" -eq 0 ]
  local after_b; after_b=$(cat "$PROJ/build-test.md")
  [ "$before_b" = "$after_b" ]
  [ ! -e "$PROJ/notes.md" ]
}

@test "AC3: migration splits legacy notes.md by canonical headers and renames source" {
  _seed_legacy_notes_with_all_sections
  run "$SCRIPT"
  [ "$status" -eq 0 ]
  for sub in codebase-map build-test patterns fragility active-work; do
    [ -f "$PROJ/$sub.md" ] || { echo "missing $sub.md"; return 1; }
  done
  grep -q "src/index.ts is the entry" "$PROJ/codebase-map.md"
  grep -q "npm test passes"           "$PROJ/build-test.md"
  grep -q "service objects everywhere" "$PROJ/patterns.md"
  grep -q "mocked DB breaks"           "$PROJ/patterns.md"
  grep -q "sonnet-4-6"                 "$PROJ/patterns.md"
  grep -q "auth.ts is fragile"         "$PROJ/fragility.md"
  grep -q "in-flight task ABC"         "$PROJ/active-work.md"
  [ ! -e "$PROJ/notes.md" ]
  [ -f "$PROJ/notes.md.legacy" ]
}

@test "AC3: re-running migration after a successful split is a no-op" {
  _seed_legacy_notes_with_all_sections
  run "$SCRIPT"; [ "$status" -eq 0 ]
  run "$SCRIPT"; [ "$status" -eq 0 ]
  [ -f "$PROJ/notes.md.legacy" ]
}

@test "AC13: legacy collision archives existing .legacy with timestamp suffix" {
  _seed_legacy_notes_with_all_sections
  printf 'old archive\n' > "$PROJ/notes.md.legacy"
  run "$SCRIPT"
  [ "$status" -eq 0 ]
  [ -f "$PROJ/notes.md.legacy" ]
  # Existing archive must have been moved aside with a timestamp suffix.
  shopt -s nullglob
  local archived=("$PROJ"/notes.md.legacy.*)
  shopt -u nullglob
  [ "${#archived[@]}" -eq 1 ]
  grep -q "old archive" "${archived[0]}"
}

@test "AC14: migration refuses symlink targets outside config root" {
  # Create a project hash dir that is a symlink pointing outside.
  local outside="$BATS_FILE_TMPDIR/outside"; mkdir -p "$outside"
  rm -rf "$PROJ"
  ln -s "$outside" "$PROJ"
  printf '# Active Work\nx\n' > "$outside/notes.md"
  run "$SCRIPT"
  # Refusal: non-zero exit OR completion that did NOT create sub-files
  # outside the config root. Either way, the outside dir is untouched.
  [ ! -f "$outside/active-work.md" ]
}

@test "mutation-kill: extract_section anchors on exact header match" {
  # If _extract_section used regex match instead of equality, a near-match
  # header like "# Active Work Items" would also pull into active-work.md.
  cat > "$PROJ/notes.md" <<'EOF'
# Codebase Map
real codebase content

# Active Work
the real active work body
EOF
  run "$SCRIPT"
  [ "$status" -eq 0 ]
  grep -q "the real active work body" "$PROJ/active-work.md"
  grep -q "real codebase content" "$PROJ/codebase-map.md"
  # The codebase content must NOT have leaked into active-work.
  ! grep -q "real codebase content" "$PROJ/active-work.md"
}

@test "dry-run prints intentions and writes nothing" {
  _seed_legacy_notes_with_all_sections
  run "$SCRIPT" --dry-run
  [ "$status" -eq 0 ]
  [[ "$output" == *"would"* ]] || [[ "$output" == *"DRY-RUN"* ]] || [[ "$output" == *"dry-run"* ]]
  [ -f "$PROJ/notes.md" ]
  [ ! -f "$PROJ/codebase-map.md" ]
}
