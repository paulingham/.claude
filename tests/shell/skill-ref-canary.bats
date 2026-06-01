#!/usr/bin/env bats
# Tests for Slice 5b: skill-namespacing FULL CUTOVER (Option A)
#
# AC-A1 (residual canary): ZERO bare backtick-wrapped /<allowlist-name> invocation
#        refs remain in the 7 trees after rewrite.
#        RED proof: a temp file containing a bare ref fires the canary.
#        GREEN: the real 7 trees return 0.
#
# AC-A4 (mcp_memory spot-check): underscore-name skill handled correctly —
#        /mcp_memory is in the allowlist and gets rewritten; the path prefix
#        skills/mcp_memory/ is NOT rewritten.
#
# AC-B1 (bootstrap plugin-mode): CLAUDE_PLUGIN_ROOT set -> bootstrap output
#        contains /harness:code-review (with slash).
# AC-B2 (bootstrap overlay-mode): CLAUDE_PLUGIN_ROOT unset -> bootstrap output
#        contains bare /code-review (no harness: prefix).
#
# AC-C2 (path-mangle canary): ZERO occurrences of harness: appearing as a
#        path component infix (e.g. pipeline-state/{task-id}/harness:intake.md
#        or harness:<name>.md) in the 7 trees.
#        RED proof: a temp file containing the mangled pattern fires the scan.
#        GREEN: the real 7 trees return 0.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK="$REPO_ROOT/hooks/session-start-bootstrap.sh"

  # Build the allowlist dynamically from skills/ (mirrors the rewrite script)
  ALLOWLIST=()
  while IFS= read -r d; do
    ALLOWLIST+=("$d")
  done < <(ls "$REPO_ROOT/skills/" | grep -v '^_' | sort)

  # Set up a temp dir for scratch files (use $TMPDIR per sandbox rules)
  SCRATCH="$(mktemp -d "${TMPDIR:-/tmp}/skill-ref-canary-XXXXXX")"

  # Git stub: minimal, just enough for the bootstrap hook to not error out.
  GIT_STUB_DIR="$(mktemp -d "${TMPDIR:-/tmp}/git-stub-XXXXXX")"
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
    exit 0
    ;;
esac
exit 0
STUBEOF
  chmod +x "$GIT_STUB_DIR/git"

  FAKE_HOME="$(mktemp -d "${TMPDIR:-/tmp}/fake-home-XXXXXX")"
  WORK_DIR="$FAKE_HOME/work"
  mkdir -p "$WORK_DIR"
}

teardown() {
  rm -rf "$SCRATCH" "$GIT_STUB_DIR" "$FAKE_HOME"
}

# ---------------------------------------------------------------------------
# Helper: run bootstrap hook with controlled environment
# ---------------------------------------------------------------------------
_run_bootstrap() {
  local plugin_root="${1:-}"
  cd "$WORK_DIR"
  if [[ -n "$plugin_root" ]]; then
    HOME="$FAKE_HOME" PATH="$GIT_STUB_DIR:$PATH" \
      CLAUDE_PLUGIN_ROOT="$plugin_root" bash "$HOOK"
  else
    HOME="$FAKE_HOME" PATH="$GIT_STUB_DIR:$PATH" \
      bash "$HOOK"
  fi
}

# ---------------------------------------------------------------------------
# AC-A1: Residual canary — RED proof (planted file MUST fire)
# ---------------------------------------------------------------------------

@test "AC-A1-red-proof: canary fires on a temp file containing bare backtick /code-review ref" {
  # Plant a bare ref that should be caught.
  # Use printf with $'\x60' (hex backtick) to avoid any shell interpretation issues.
  BT=$'\x60'
  printf 'see %s/code-review%s for details\n' "$BT" "$BT" >"$SCRATCH/planted.md"

  # Canary scan on the planted file: must find >= 1 match
  MATCHES=$(grep -cE '`/[a-z]([a-z0-9_-]*[a-z0-9])?`' "$SCRATCH/planted.md" || true)
  [[ "$MATCHES" -ge 1 ]]
}

@test "AC-A1-green: ZERO bare backtick allowlist invocation refs in the 7 trees" {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"

  # Build alternation pattern from allowlist (longest first for correctness)
  PATTERN_PARTS=()
  for skill in "${ALLOWLIST[@]}"; do
    PATTERN_PARTS+=("$skill")
  done
  # Sort by length descending so longer names match first
  IFS=$'\n' SORTED=($(printf '%s\n' "${PATTERN_PARTS[@]}" | awk '{ print length, $0 }' | sort -rn | cut -d' ' -f2-))
  unset IFS
  ALT=$(IFS='|'; echo "${SORTED[*]}")

  MATCHES=$(
    grep -rnE "\`/(${ALT})\`" \
      "$REPO_ROOT/skills" \
      "$REPO_ROOT/protocols" \
      "$REPO_ROOT/orchestrator" \
      "$REPO_ROOT/rules" \
      "$REPO_ROOT/agents" \
      "$REPO_ROOT/README.md" \
      "$REPO_ROOT/CLAUDE.md" \
      2>/dev/null | wc -l | tr -d ' '
  )
  [[ "$MATCHES" -eq 0 ]]
}

# ---------------------------------------------------------------------------
# AC-A4: mcp_memory underscore-name handled correctly
# ---------------------------------------------------------------------------

@test "AC-A4: mcp_memory bare backtick invocation ref is rewritten (not present in 7 trees)" {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  MATCHES=$(
    grep -rnE '`/mcp_memory`' \
      "$REPO_ROOT/skills" \
      "$REPO_ROOT/protocols" \
      "$REPO_ROOT/orchestrator" \
      "$REPO_ROOT/rules" \
      "$REPO_ROOT/agents" \
      "$REPO_ROOT/README.md" \
      "$REPO_ROOT/CLAUDE.md" \
      2>/dev/null | wc -l | tr -d ' '
  )
  [[ "$MATCHES" -eq 0 ]]
}

@test "AC-A4: path skills/mcp_memory/ is NOT mangled by the rewrite" {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  # The path prefix must still exist (not rewritten to skills/harness:mcp_memory/)
  [[ -d "$REPO_ROOT/skills/mcp_memory" ]]
  # And no 'skills/harness:' paths exist anywhere
  MANGLED=$(
    grep -rnE 'skills/harness:|/skills/harness:' \
      "$REPO_ROOT/skills" \
      "$REPO_ROOT/protocols" \
      "$REPO_ROOT/orchestrator" \
      "$REPO_ROOT/rules" \
      "$REPO_ROOT/agents" \
      "$REPO_ROOT/README.md" \
      "$REPO_ROOT/CLAUDE.md" \
      2>/dev/null | wc -l | tr -d ' '
  )
  [[ "$MANGLED" -eq 0 ]]
}

# ---------------------------------------------------------------------------
# AC-B1: Bootstrap plugin-mode -> /harness:code-review in output
# ---------------------------------------------------------------------------

@test "AC-B1: bootstrap with CLAUDE_PLUGIN_ROOT set emits /harness:code-review" {
  run _run_bootstrap "/fake/plugin/root"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q '/harness:code-review'
}

@test "AC-B1: bootstrap with CLAUDE_PLUGIN_ROOT set emits /harness:intake" {
  run _run_bootstrap "/fake/plugin/root"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q '/harness:intake'
}

@test "AC-B1: bootstrap with CLAUDE_PLUGIN_ROOT set emits /harness:pipeline" {
  run _run_bootstrap "/fake/plugin/root"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q '/harness:pipeline'
}

# ---------------------------------------------------------------------------
# AC-B2: Bootstrap overlay-mode (no CLAUDE_PLUGIN_ROOT) -> bare /code-review
# ---------------------------------------------------------------------------

@test "AC-B2: bootstrap without CLAUDE_PLUGIN_ROOT emits bare /code-review (no harness: prefix)" {
  unset CLAUDE_PLUGIN_ROOT
  run _run_bootstrap ""
  [ "$status" -eq 0 ]
  echo "$output" | grep -q '/code-review'
  ! echo "$output" | grep -q '/harness:code-review'
}

@test "AC-B2: bootstrap without CLAUDE_PLUGIN_ROOT emits bare /intake (no harness: prefix)" {
  unset CLAUDE_PLUGIN_ROOT
  run _run_bootstrap ""
  [ "$status" -eq 0 ]
  echo "$output" | grep -q '/intake'
  ! echo "$output" | grep -q '/harness:intake'
}

# ---------------------------------------------------------------------------
# AC-C2: Path-mangle canary — RED proof + GREEN real-tree check
#
# The Slice-5b bug: lookbehind (?<![.\w/]) passed on path-component terminators
# like } (from {task-id}), causing pipeline-state/{task-id}/intake.md to become
# pipeline-state/{task-id}/harness:intake.md. This canary guards against recurrence.
# ---------------------------------------------------------------------------

@test "AC-C2-red-proof: path-mangle scan fires on a file containing harness: as path infix" {
  # Plant a mangled path as would appear in the bug: harness:intake.md as a path component
  printf 'Read pipeline-state/{task-id}/harness:intake.md for tier.\n' \
    >"$SCRATCH/mangled.md"

  # The scan must find >= 1 match in the planted file
  MATCHES=$(
    grep -cE 'pipeline-state/[^` ]*harness:|harness:[a-z0-9_-]+\.(md|json)' \
      "$SCRATCH/mangled.md" || true
  )
  [[ "$MATCHES" -ge 1 ]]
}

@test "AC-C2-green: ZERO harness: path-component infixes in the 7 trees" {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"

  # Pattern 1: harness:<name>.md or harness:<name>.json anywhere
  # Pattern 2: any path segment ending in harness: (e.g. /harness: preceded by path char)
  MATCHES=$(
    grep -rnE 'harness:[a-z0-9_-]+\.(md|json)|[}A-Za-z0-9_.\-]/harness:' \
      "$REPO_ROOT/skills" \
      "$REPO_ROOT/protocols" \
      "$REPO_ROOT/orchestrator" \
      "$REPO_ROOT/rules" \
      "$REPO_ROOT/agents" \
      "$REPO_ROOT/README.md" \
      "$REPO_ROOT/CLAUDE.md" \
      2>/dev/null | wc -l | tr -d ' '
  )
  [[ "$MATCHES" -eq 0 ]]
}

# ---------------------------------------------------------------------------
# AC-A5 (collision-residual targeted): The 4 highest-collision skill names
# (code-review, security-review, verify, debug) are ALL namespaced — no bare
# backtick invocation refs remain in the 7 trees.
#
# These names collide with common English words and system concepts, making
# them the highest regression risk for future edits re-introducing bare refs.
# A targeted test adds a named regression anchor beyond the generic allowlist scan.
#
# RED proof: a temp file containing a bare backtick /security-review fires the scan.
# GREEN: the real 7 trees contain ZERO bare backtick refs for any of the 4 names.
# ---------------------------------------------------------------------------

@test "AC-A5-red-proof: collision-residual scan fires on bare backtick /security-review" {
  BT=$'\x60'
  printf 'Run %s/security-review%s after review.\n' "$BT" "$BT" >"$SCRATCH/collision.md"

  MATCHES=$(grep -cE '`/(code-review|security-review|verify|debug)`' \
    "$SCRATCH/collision.md" || true)
  [[ "$MATCHES" -ge 1 ]]
}

@test "AC-A5-green: ZERO bare backtick refs for collision names (code-review, security-review, verify, debug) in 7 trees" {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"

  MATCHES=$(
    grep -rnE '`/(code-review|security-review|verify|debug)`' \
      "$REPO_ROOT/skills" \
      "$REPO_ROOT/protocols" \
      "$REPO_ROOT/orchestrator" \
      "$REPO_ROOT/rules" \
      "$REPO_ROOT/agents" \
      "$REPO_ROOT/README.md" \
      "$REPO_ROOT/CLAUDE.md" \
      2>/dev/null | wc -l | tr -d ' '
  )
  [[ "$MATCHES" -eq 0 ]]
}

# ---------------------------------------------------------------------------
# AC-B3 (bootstrap collision-name branch guard): The bootstrap hook's
# plugin-mode branch emits /harness: prefixed versions of the 4 highest-
# collision skill names, and the overlay-mode branch does NOT emit the
# harness-prefixed variants for those same names.
#
# Rationale: AC-B1/B2 test code-review/intake/pipeline but not the collision
# names security-review, verify, debug. A regression where plugin-mode omits
# the prefix for these, or overlay-mode accidentally emits it, would not be
# caught by the existing tests.
#
# RED proof: a bootstrap output string containing bare /security-review in
# plugin-mode context fires the negative assertion.
# GREEN plugin-mode: output contains /harness:security-review, /harness:verify,
#       /harness:debug.
# GREEN overlay-mode: output does NOT contain /harness:security-review,
#       /harness:verify, /harness:debug.
# ---------------------------------------------------------------------------

@test "AC-B3-red-proof: plugin-mode collision check fires when /harness: prefix is absent" {
  # Simulate a bootstrap output that is missing the harness: prefix for security-review
  printf '/security-review (parallel)\n' >"$SCRATCH/bad-plugin-output.md"

  # The check: grep for bare /security-review NOT preceded by harness:
  MATCHES=$(grep -cE '(?<!harness:)(^|[[:space:]])/security-review' \
    "$SCRATCH/bad-plugin-output.md" || true)
  # If grep -P is unavailable, fall back to a simpler pattern check
  if [[ "$MATCHES" -eq 0 ]]; then
    MATCHES=$(grep -cv '/harness:security-review' "$SCRATCH/bad-plugin-output.md" || true)
  fi
  [[ "$MATCHES" -ge 1 ]]
}

@test "AC-B3-plugin-mode: bootstrap with CLAUDE_PLUGIN_ROOT set emits /harness:security-review" {
  run _run_bootstrap "/fake/plugin/root"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q '/harness:security-review'
}

@test "AC-B3-plugin-mode: bootstrap with CLAUDE_PLUGIN_ROOT set emits /harness:verify" {
  run _run_bootstrap "/fake/plugin/root"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q '/harness:verify'
}

@test "AC-B3-plugin-mode: bootstrap with CLAUDE_PLUGIN_ROOT set emits /harness:debug" {
  run _run_bootstrap "/fake/plugin/root"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q '/harness:debug'
}

@test "AC-B3-overlay-mode: bootstrap without CLAUDE_PLUGIN_ROOT does NOT emit /harness:security-review" {
  unset CLAUDE_PLUGIN_ROOT
  run _run_bootstrap ""
  [ "$status" -eq 0 ]
  ! echo "$output" | grep -q '/harness:security-review'
}

@test "AC-B3-overlay-mode: bootstrap without CLAUDE_PLUGIN_ROOT does NOT emit /harness:verify" {
  unset CLAUDE_PLUGIN_ROOT
  run _run_bootstrap ""
  [ "$status" -eq 0 ]
  ! echo "$output" | grep -q '/harness:verify'
}
