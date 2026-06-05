#!/usr/bin/env bats
# AC4 + AC5 shell contract tests for hooks/phase-boundary-compress.sh
# WRITTEN BEFORE IMPLEMENTATION (RED).
#
# AC4: Advisory by default; escape hatch CLAUDE_DISABLE_PHASE_BOUNDARY_COMPRESS=1 exits 0 cleanly.
# AC5: Self-contained — grep for phase-boundary-compress outside allowlist returns nothing.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK="$REPO_ROOT/hooks/phase-boundary-compress.sh"
  TMP="$(mktemp -d -t pbc.XXXXXX)"
  # Provide harness path stubs so the hook can source them
  export CLAUDE_PLUGIN_ROOT="$REPO_ROOT"
  export CLAUDE_PLUGIN_DATA="$TMP/harness-data"
  export CLAUDE_STATE_DIR="$TMP/state"
  export CLAUDE_SESSION_ID="test-session-$$"
  mkdir -p "$CLAUDE_PLUGIN_DATA/metrics/$CLAUDE_SESSION_ID"
  mkdir -p "$CLAUDE_STATE_DIR"
}

teardown() {
  [ -d "$TMP" ] && rm -rf "$TMP"
}

# ---------------------------------------------------------------------------
# AC4 — Escape hatch: CLAUDE_DISABLE_PHASE_BOUNDARY_COMPRESS=1 → exit 0, no emit
# ---------------------------------------------------------------------------

@test "AC4.1 escape hatch exits 0 with no metrics file created" {
  export CLAUDE_DISABLE_PHASE_BOUNDARY_COMPRESS=1
  run "$HOOK" "build" "security-review"
  [ "$status" -eq 0 ]
  [ ! -f "$CLAUDE_PLUGIN_DATA/metrics/$CLAUDE_SESSION_ID/phase-boundary.jsonl" ]
}

@test "AC4.2 escape hatch produces no output" {
  export CLAUDE_DISABLE_PHASE_BOUNDARY_COMPRESS=1
  run "$HOOK" "build" "security-review"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "AC4.3 default (unset) exits 0 — advisory, does not block" {
  unset CLAUDE_DISABLE_PHASE_BOUNDARY_COMPRESS
  # Supply a minimal handoff via stdin or tmp file — hook reads from args
  run "$HOOK" "build" "security-review"
  [ "$status" -eq 0 ]
}

@test "AC4.4 default (unset) emits one record to phase-boundary.jsonl" {
  unset CLAUDE_DISABLE_PHASE_BOUNDARY_COMPRESS
  run "$HOOK" "build" "security-review"
  [ "$status" -eq 0 ]
  [ -f "$CLAUDE_PLUGIN_DATA/metrics/$CLAUDE_SESSION_ID/phase-boundary.jsonl" ]
}

@test "AC4.5 advisory mode does not rewrite a handoff file passed as arg 3" {
  unset CLAUDE_DISABLE_PHASE_BOUNDARY_COMPRESS
  # Write a handoff file and verify it is unchanged after the hook runs
  HANDOFF_FILE="$TMP/handoff.md"
  printf '## Goal\n\nTest goal.\n\n## Key Findings\n\n- Finding 1.\n' > "$HANDOFF_FILE"
  ORIGINAL_CONTENT="$(cat "$HANDOFF_FILE")"
  run "$HOOK" "build" "security-review" "$HANDOFF_FILE"
  [ "$status" -eq 0 ]
  [ "$(cat "$HANDOFF_FILE")" = "$ORIGINAL_CONTENT" ]
}

# ---------------------------------------------------------------------------
# AC5 — Self-contained: no references outside the allowlist
# ---------------------------------------------------------------------------

@test "AC5.1 no coupling outside allowlist files" {
  # Allowlist: the 2 new files, the 2 protocol docs, the SKILL stanza
  # Everything else must not reference phase-boundary-compress
  ALLOWLIST=(
    "$REPO_ROOT/hooks/phase-boundary-compress.sh"
    "$REPO_ROOT/hooks/_lib/phase_boundary_tokens.py"
    "$REPO_ROOT/protocols/pipeline-protocol.md"
    "$REPO_ROOT/protocols/cost-discipline.md"
    "$REPO_ROOT/skills/pipeline/SKILL.md"
    "$REPO_ROOT/tests/shell/test_phase_boundary_compress.bats"
    "$REPO_ROOT/tests/test_phase_boundary_tokens.py"
  )

  # Build grep exclusion args
  GREP_ARGS=()
  for f in "${ALLOWLIST[@]}"; do
    GREP_ARGS+=("--exclude=$(basename "$f")")
  done

  # grep -rl in the repo root, excluding allowlist basenames
  result=$(grep -rl "phase-boundary-compress" "$REPO_ROOT" \
    --include="*.sh" \
    --include="*.py" \
    --include="*.md" \
    --include="*.bats" \
    "${GREP_ARGS[@]}" 2>/dev/null || true)

  [ -z "$result" ] || {
    echo "Unexpected coupling found:"
    echo "$result"
    false
  }
}
