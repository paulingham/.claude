#!/usr/bin/env bats
# AC23 + AC24 (Slice D) — session-memory-updater-dispatch.sh permanently
# refuses spawns targeting codebase-map BEFORE the seed-on-miss branch fires.
#
# Two ACs:
# - AC23: invocation with codebase-map targetSection exits 1 with structured
#   JSON `{"error":"generated_artifact_misroute","action":"spawn_refused"}`.
# - AC24: refusal fires BEFORE seed-on-miss — pre-deleting the target file
#   does NOT cause the script to copy a template; it exits 1 immediately.
#
# bats `run` merges stderr into $output (no --separate-stderr in 1.13), so
# the JSON-error checks grep $output.

setup() {
  BATS_FILE_TMPDIR="$(mktemp -d -t sm-codemap.XXXXXX)"
  TEST_HOME="$BATS_FILE_TMPDIR/home"; mkdir -p "$TEST_HOME"
  export HOME="$TEST_HOME"
  export CLAUDE_CONFIG_DIR="$TEST_HOME/.claude"
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  DISPATCH="$REPO_ROOT/hooks/_lib/session-memory-updater-dispatch.sh"

  # Mirror real harness layout: stage a fake template so seed-on-miss WOULD
  # have fired had the new branch not pre-empted it. If the refusal really
  # fires first, the template never gets copied.
  TEMPLATE_DIR="$CLAUDE_CONFIG_DIR/session-memory/config/templates"
  mkdir -p "$TEMPLATE_DIR"
  printf '%s\n' '# Codebase Map' '_test template body — should NEVER be copied to a target_' \
    > "$TEMPLATE_DIR/codebase-map.md"
  printf '%s\n' '# Patterns' '_patterns template_' \
    > "$TEMPLATE_DIR/patterns.md"

  PROJECT_DIR="$BATS_FILE_TMPDIR/proj"
  mkdir -p "$PROJECT_DIR"
  TARGET_FILE="$PROJECT_DIR/codebase-map.md"
}

teardown() { rm -rf "$BATS_FILE_TMPDIR"; }

@test "refuses codebase-map dispatch with structured error" {
  # AC23: exit 1 + JSON error to stderr (merged into $output by bats `run`).
  run bash "$DISPATCH" "$TARGET_FILE" "codebase-map"
  [ "$status" -eq 1 ]
  echo "$output" | grep -q '"error":"generated_artifact_misroute"'
  echo "$output" | grep -q '"action":"spawn_refused"'
}

@test "refusal fires before seed-on-miss" {
  # AC24: pre-delete the target so seed-on-miss WOULD trigger; the new
  # refusal branch must short-circuit BEFORE that branch and NOT copy
  # the template into TARGET_FILE.
  rm -f "$TARGET_FILE"
  [ ! -e "$TARGET_FILE" ]

  run bash "$DISPATCH" "$TARGET_FILE" "codebase-map"
  [ "$status" -eq 1 ]
  # Refusal returned BEFORE seed-on-miss copied the template:
  [ ! -e "$TARGET_FILE" ]
  # And the structured-error envelope identifies the refusal kind:
  echo "$output" | grep -q 'generated_artifact_misroute'
}

@test "non-codebase-map dispatch unaffected (regression guard)" {
  # patterns dispatch still works — refusal must be codebase-map-specific.
  run bash "$DISPATCH" "$PROJECT_DIR/patterns.md" "patterns"
  # Either succeeds (template was seeded) or benignly reports template_missing
  # / seed_failed; neither path should yield the new misroute envelope.
  ! echo "$output" | grep -q 'generated_artifact_misroute'
}
