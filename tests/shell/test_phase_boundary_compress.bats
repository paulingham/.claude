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

# ---------------------------------------------------------------------------
# Security Fix 1 — SESSION_ID sanitization: path-traversal prevention
# ---------------------------------------------------------------------------

@test "SEC1.1 crafted session-id with ../ does not escape metrics tree" {
  unset CLAUDE_DISABLE_PHASE_BOUNDARY_COMPRESS
  # A crafted session id that would attempt path traversal
  export CLAUDE_SESSION_ID="../../evil"
  run "$HOOK" "build" "security-review"
  [ "$status" -eq 0 ]
  # The metrics file must NOT appear at the traversal target
  [ ! -f "$CLAUDE_PLUGIN_DATA/evil/phase-boundary.jsonl" ]
  [ ! -f "$TMP/evil/phase-boundary.jsonl" ]
  # And no file should exist outside the CLAUDE_PLUGIN_DATA/metrics/ subtree
  evil_file=$(find "$TMP" -name "phase-boundary.jsonl" \
    ! -path "$CLAUDE_PLUGIN_DATA/metrics/*" 2>/dev/null || true)
  [ -z "$evil_file" ] || {
    echo "File written outside metrics tree: $evil_file"
    false
  }
}

@test "SEC1.2 sanitized session-id still produces a metrics file under metrics tree" {
  unset CLAUDE_DISABLE_PHASE_BOUNDARY_COMPRESS
  export CLAUDE_SESSION_ID="../../evil"
  run "$HOOK" "build" "security-review"
  [ "$status" -eq 0 ]
  # Some file must have been written somewhere under metrics/
  found=$(find "$CLAUDE_PLUGIN_DATA/metrics" -name "phase-boundary.jsonl" 2>/dev/null || true)
  [ -n "$found" ] || {
    echo "No phase-boundary.jsonl found under metrics tree after sanitization"
    false
  }
}

@test "SEC1.3 all-slash session-id falls back to local-PID safe default" {
  unset CLAUDE_DISABLE_PHASE_BOUNDARY_COMPRESS
  export CLAUDE_SESSION_ID="///"
  run "$HOOK" "build" "security-review"
  [ "$status" -eq 0 ]
  # Must not have written outside the metrics tree
  evil_file=$(find "$TMP" -name "phase-boundary.jsonl" \
    ! -path "$CLAUDE_PLUGIN_DATA/metrics/*" 2>/dev/null || true)
  [ -z "$evil_file" ] || { echo "Escape: $evil_file"; false; }
}

# ---------------------------------------------------------------------------
# AC5 — Self-contained: no references outside the allowlist
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Final-Gate condition 2 — honest advisory log
# ---------------------------------------------------------------------------

@test "FG2.1 'recorded' message appears only when JSONL line was actually written" {
  unset CLAUDE_DISABLE_PHASE_BOUNDARY_COMPRESS
  HANDOFF_FILE="$TMP/handoff.md"
  printf '## Goal\n\nTest.\n\n## Key Findings\n\n- F1.\n' > "$HANDOFF_FILE"
  run "$HOOK" "build" "security-review" "$HANDOFF_FILE"
  [ "$status" -eq 0 ]
  # A JSONL file must exist — confirms "recorded" is truthful here
  [ -f "$CLAUDE_PLUGIN_DATA/metrics/$CLAUDE_SESSION_ID/phase-boundary.jsonl" ]
  # The stderr output must contain "recorded"
  [[ "$output" == *"recorded"* ]] || [[ "$stderr" == *"recorded"* ]]
}

@test "FG2.2 'skipped' message appears when metrics dir is unwritable" {
  unset CLAUDE_DISABLE_PHASE_BOUNDARY_COMPRESS
  # Make the metrics dir unwritable so Python cannot create the file
  METRICS_PARENT="$CLAUDE_PLUGIN_DATA/metrics/$CLAUDE_SESSION_ID"
  mkdir -p "$METRICS_PARENT"
  chmod 000 "$METRICS_PARENT"
  HANDOFF_FILE="$TMP/handoff.md"
  printf '## Goal\n\nTest.\n\n## Key Findings\n\n- F1.\n' > "$HANDOFF_FILE"
  run "$HOOK" "build" "security-review" "$HANDOFF_FILE"
  # Restore permissions for teardown
  chmod 755 "$METRICS_PARENT"
  [ "$status" -eq 0 ]
  # No JSONL written — must say "skipped", not "recorded"
  [[ "$output" == *"skipped"* ]] || [[ "$stderr" == *"skipped"* ]]
}

@test "AC5.1 no coupling outside allowlist files" {
  # Allowlist: exact absolute paths that ARE permitted to reference phase-boundary-compress.
  # We grep for all matches first, then post-filter out the exact allowed paths.
  # This catches coupling sneaked into any other SKILL.md or any other file.
  ALLOWLIST_EXACT=(
    "$REPO_ROOT/hooks/phase-boundary-compress.sh"
    "$REPO_ROOT/hooks/_lib/phase_boundary_tokens.py"
    "$REPO_ROOT/hooks/tests/test-hook-registration-invariant.sh"
    "$REPO_ROOT/protocols/pipeline-protocol.md"
    "$REPO_ROOT/protocols/cost-discipline.md"
    "$REPO_ROOT/skills/pipeline/SKILL.md"
    "$REPO_ROOT/tests/shell/test_phase_boundary_compress.bats"
    "$REPO_ROOT/tests/test_phase_boundary_tokens.py"
  )

  # Collect all matching files (full paths)
  all_matches=$(grep -rl "phase-boundary-compress" "$REPO_ROOT" \
    --include="*.sh" \
    --include="*.py" \
    --include="*.md" \
    --include="*.bats" \
    2>/dev/null || true)

  # Remove each allowlisted path from the match list
  remaining="$all_matches"
  for allowed in "${ALLOWLIST_EXACT[@]}"; do
    remaining=$(printf '%s\n' "$remaining" | grep -vxF "$allowed" || true)
  done

  # Anything left is unexpected coupling
  [ -z "$remaining" ] || {
    echo "Unexpected coupling found outside allowlist:"
    echo "$remaining"
    false
  }
}
