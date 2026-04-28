#!/usr/bin/env bats
# Specs for hooks/session-start-bootstrap.sh — per-project instinct directory
# bootstrap and LEARN HINT behaviour.
#
# Hermetic: each test sets up FAKE_HOME and a git stub so the hook resolves a
# deterministic project hash and never touches the real filesystem.
# Deterministic project hash for the stubbed remote URL:
#   printf 'https://github.com/test-org/test-repo.git\n' | md5sum | awk '{print $1}'
#   = 61be120c28022104871d7ec0d7bdf5be

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK="$REPO_ROOT/hooks/session-start-bootstrap.sh"
  SKILL_LEARN="$REPO_ROOT/skills/learn/SKILL.md"

  FAKE_HOME="$(mktemp -d)"
  GIT_STUB_DIR="$(mktemp -d)"
  PROJECT_HASH="61be120c28022104871d7ec0d7bdf5be"
  LEARNING_DIR="$FAKE_HOME/.claude/learning"
  PROJECT_INSTINCTS_DIR="$LEARNING_DIR/$PROJECT_HASH/instincts"
  GLOBAL_INSTINCTS_DIR="$LEARNING_DIR/instincts"
  OBSERVATIONS_FILE="$LEARNING_DIR/$PROJECT_HASH/observations.jsonl"

  # Git stub: returns a deterministic remote URL and harmless responses for
  # the other subcommands the hook calls (rev-parse --git-dir,
  # worktree list --porcelain, rev-parse --show-toplevel). No .claude/worktrees/
  # lines appear in the worktree-list output, so the stale-worktree warning
  # branch never fires.
  cat >"$GIT_STUB_DIR/git" <<'STUBEOF'
#!/usr/bin/env bash
case "$1 $2 $3" in
  "remote get-url origin")
    printf 'https://github.com/test-org/test-repo.git'
    exit 0
    ;;
  "rev-parse --git-dir ")
    echo ".git"
    exit 0
    ;;
  "worktree list --porcelain")
    echo "worktree /tmp/fake-main"
    echo "HEAD 0000000000000000000000000000000000000000"
    echo "branch refs/heads/main"
    exit 0
    ;;
  "rev-parse --show-toplevel ")
    # Return empty so the automation.env probe at the top of the hook
    # falls through cleanly.
    exit 0
    ;;
esac
exit 0
STUBEOF
  chmod +x "$GIT_STUB_DIR/git"

  # Always run the hook from a clean working dir under FAKE_HOME so the
  # automation.env probe (line 37 of the hook) finds nothing.
  WORK_DIR="$FAKE_HOME/work"
  mkdir -p "$WORK_DIR"
}

teardown() {
  rm -rf "$FAKE_HOME" "$GIT_STUB_DIR"
}

# Helper: run the hook with FAKE_HOME and the git stub on PATH.
_run_hook() {
  cd "$WORK_DIR"
  HOME="$FAKE_HOME" PATH="$GIT_STUB_DIR:$PATH" bash "$HOOK"
}

# Helper: write a valid instinct fixture file. The hook greps for
# 'confidence:' and '## Pattern' so both must appear.
_write_instinct() {
  local file="$1"
  cat >"$file" <<'INEOF'
---
id: test-instinct
confidence: 0.7
roles: [software-engineer]
---

## Pattern

This is a test pattern that the hook will display.

## Evidence

irrelevant
INEOF
}

# ---------------------------------------------------------------------------
# AC-dir-created — hook creates the per-project instincts directory
# ---------------------------------------------------------------------------

@test "AC-dir-created: instincts dir is created on first run when absent" {
  [ ! -d "$PROJECT_INSTINCTS_DIR" ]
  run _run_hook
  [ "$status" -eq 0 ]
  [ -d "$PROJECT_INSTINCTS_DIR" ]
}

# ---------------------------------------------------------------------------
# AC-dir-idempotent — running twice doesn't error and doesn't duplicate hints
# ---------------------------------------------------------------------------

@test "AC-dir-idempotent: second run is a no-op (dir still exists, no duplicate LEARN HINT)" {
  # Seed observations so a LEARN HINT would fire on each run.
  mkdir -p "$LEARNING_DIR/$PROJECT_HASH"
  printf '{"r":1}\n{"r":2}\n{"r":3}\n' >"$OBSERVATIONS_FILE"

  run _run_hook
  [ "$status" -eq 0 ]
  [ -d "$PROJECT_INSTINCTS_DIR" ]
  first_hint_count=$(echo "$output" | grep -c "^LEARN HINT:")
  [ "$first_hint_count" -eq 1 ]

  # Second run: directory already exists; LEARN HINT must still fire exactly once.
  run _run_hook
  [ "$status" -eq 0 ]
  [ -d "$PROJECT_INSTINCTS_DIR" ]
  second_hint_count=$(echo "$output" | grep -c "^LEARN HINT:")
  [ "$second_hint_count" -eq 1 ]
}

# ---------------------------------------------------------------------------
# AC-learn-hint-emitted — >=3 observations and no instincts -> exactly one hint
# ---------------------------------------------------------------------------

@test "AC-learn-hint-emitted: 3 observations + empty instincts dir emits LEARN HINT with count" {
  mkdir -p "$LEARNING_DIR/$PROJECT_HASH"
  printf 'a\nb\nc\n' >"$OBSERVATIONS_FILE"

  run _run_hook
  [ "$status" -eq 0 ]
  echo "$output" | grep -q "^LEARN HINT: 3 observations without instincts"
}

# ---------------------------------------------------------------------------
# AC-learn-hint-suppressed-by-instinct — instinct present -> no hint
# ---------------------------------------------------------------------------

@test "AC-learn-hint-suppressed-by-instinct: instinct file present suppresses LEARN HINT" {
  mkdir -p "$PROJECT_INSTINCTS_DIR" "$LEARNING_DIR/$PROJECT_HASH"
  _write_instinct "$PROJECT_INSTINCTS_DIR/test.md"
  # Plenty of observations — would normally trigger a hint, but per-project
  # instinct presence must suppress it.
  printf 'a\nb\nc\nd\ne\n' >"$OBSERVATIONS_FILE"

  run _run_hook
  [ "$status" -eq 0 ]
  ! echo "$output" | grep -q "^LEARN HINT:"
}

# ---------------------------------------------------------------------------
# AC-learn-hint-suppressed-below-threshold — <3 observations -> no hint
# ---------------------------------------------------------------------------

@test "AC-learn-hint-suppressed-below-threshold: 2 observations and no instincts emits no LEARN HINT" {
  mkdir -p "$LEARNING_DIR/$PROJECT_HASH"
  printf 'a\nb\n' >"$OBSERVATIONS_FILE"

  run _run_hook
  [ "$status" -eq 0 ]
  ! echo "$output" | grep -q "^LEARN HINT:"
}

# ---------------------------------------------------------------------------
# AC-learn-hint-once — many observations -> exactly one hint line
# ---------------------------------------------------------------------------

@test "AC-learn-hint-once: LEARN HINT appears exactly once with many observations" {
  mkdir -p "$LEARNING_DIR/$PROJECT_HASH"
  # 50 observation lines.
  for _ in $(seq 1 50); do echo "obs"; done >"$OBSERVATIONS_FILE"

  run _run_hook
  [ "$status" -eq 0 ]
  hint_count=$(echo "$output" | grep -c "^LEARN HINT:")
  [ "$hint_count" -eq 1 ]
  echo "$output" | grep -q "^LEARN HINT: 50 observations without instincts"
}

# ---------------------------------------------------------------------------
# AC-prefer-project-over-global — per-project instincts win over global
# ---------------------------------------------------------------------------

@test "AC-prefer-project-over-global: LEARNED PATTERNS shows per-project count when both dirs populated" {
  mkdir -p "$PROJECT_INSTINCTS_DIR" "$GLOBAL_INSTINCTS_DIR"
  _write_instinct "$PROJECT_INSTINCTS_DIR/proj.md"
  # Two global instincts to make the count differ from the per-project count (1).
  _write_instinct "$GLOBAL_INSTINCTS_DIR/g1.md"
  _write_instinct "$GLOBAL_INSTINCTS_DIR/g2.md"

  run _run_hook
  [ "$status" -eq 0 ]
  echo "$output" | grep -q "^LEARNED PATTERNS (1 instincts):"
  ! echo "$output" | grep -q "^LEARNED PATTERNS (2 instincts):"
}

# ---------------------------------------------------------------------------
# AC-global-fallback — global instincts shown when per-project dir is empty
# ---------------------------------------------------------------------------

@test "AC-global-fallback: empty per-project dir falls back to global instincts" {
  mkdir -p "$PROJECT_INSTINCTS_DIR" "$GLOBAL_INSTINCTS_DIR"
  _write_instinct "$GLOBAL_INSTINCTS_DIR/g1.md"
  _write_instinct "$GLOBAL_INSTINCTS_DIR/g2.md"

  run _run_hook
  [ "$status" -eq 0 ]
  echo "$output" | grep -q "^LEARNED PATTERNS (2 instincts):"
}

# ---------------------------------------------------------------------------
# AC-learn-skill-bootstrap — /learn skill documents the mkdir contract
# ---------------------------------------------------------------------------

@test "AC-learn-skill-bootstrap: skills/learn/SKILL.md contains mkdir -p targeting instincts directory" {
  # Grep-level contract: the skill must document creating the per-project
  # instincts dir so the hook + skill agree on the bootstrap location.
  grep -E 'mkdir -p .*instincts' "$SKILL_LEARN"
}
