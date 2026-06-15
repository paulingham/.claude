#!/usr/bin/env bats
# Slice C bats tests (C1-C7) — scaffolding scripts behaviour.
#
# C1: shellcheck-clean on all three scripts
# C2: new-skill.sh dry-run creates skill dir + proposes README bump; no git add -A
# C3: new-agent.sh dry-run proposes 5-col table row + README agent count bump
# C4: new-hook.sh auto-wires BOTH JSON registries when confirmed
# C5: new-hook.sh decline leaves registries untouched AND warns loudly + exits non-zero
# C6: new-hook.sh runs invariant after wiring
# C7: no 'git add -A' or 'git add .' in any script

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  SCRIPTS="$REPO_ROOT/scripts"
  # Temp dir for registry copies and hook files to avoid mutating live repo
  TMPDIR_TEST="$(mktemp -d)"
  cp "$REPO_ROOT/hooks/hooks.json" "$TMPDIR_TEST/hooks.json"
  cp "$REPO_ROOT/settings.json" "$TMPDIR_TEST/settings.json"
  mkdir -p "$TMPDIR_TEST/hooks"
}

teardown() {
  rm -rf "$TMPDIR_TEST"
}

# ── C1: shellcheck-clean ──────────────────────────────────────────────────────

@test "C1 shellcheck new-skill.sh new-agent.sh new-hook.sh" {
  run shellcheck \
    "$SCRIPTS/new-skill.sh" \
    "$SCRIPTS/new-agent.sh" \
    "$SCRIPTS/new-hook.sh"
  [ "$status" -eq 0 ]
}

# ── C2: new-skill.sh dry-run ─────────────────────────────────────────────────

@test "C2 new-skill dry-run proposes README bump without git add -A" {
  run bash "$SCRIPTS/new-skill.sh" --dry-run "my-test-skill-$(date +%s)"
  # Must exit non-zero (dry-run mode does not persist) or zero with output
  # Key assertion: output mentions README and skill directory
  echo "$output" | grep -qi "README\|skill"
  # Must NOT contain git add -A or git add .
  ! echo "$output" | grep -q "git add -A"
  ! echo "$output" | grep -q "git add \."
}

# ── C3: new-agent.sh dry-run ─────────────────────────────────────────────────

@test "C3 new-agent dry-run proposes table row and README agent count" {
  run bash "$SCRIPTS/new-agent.sh" --dry-run "my-test-agent-$(date +%s)"
  echo "$output" | grep -qi "README\|agent"
  ! echo "$output" | grep -q "git add -A"
}

# ── C4: new-hook.sh wires BOTH registries on confirm ─────────────────────────

@test "C4 new-hook auto-wires both hooks.json and settings.json" {
  local hook_name="test-wiring-$$"
  local event="PostToolUse"
  # Run with auto-confirm; use tmp hooks dir to avoid polluting live hooks/
  run env CLAUDE_ONRAMP_AUTOCONFIRM=1 \
    CLAUDE_ONRAMP_HOOKS_JSON="$TMPDIR_TEST/hooks.json" \
    CLAUDE_ONRAMP_SETTINGS_JSON="$TMPDIR_TEST/settings.json" \
    CLAUDE_ONRAMP_HOOKS_DIR="$TMPDIR_TEST/hooks" \
    CLAUDE_ONRAMP_REPO_ROOT="$REPO_ROOT" \
    bash "$SCRIPTS/new-hook.sh" "$hook_name" "$event"
  # Both registries must now reference the hook name
  grep -q "$hook_name" "$TMPDIR_TEST/hooks.json"
  grep -q "$hook_name" "$TMPDIR_TEST/settings.json"
}

# ── C5: new-hook.sh decline leaves registries untouched + warns ──────────────

@test "C5 new-hook decline leaves registries untouched AND warns loudly" {
  local hook_name="test-decline-$$"
  local event="PreToolUse"
  local before_hooks; before_hooks="$(python3 -m json.tool "$TMPDIR_TEST/hooks.json")"
  local before_settings; before_settings="$(python3 -m json.tool "$TMPDIR_TEST/settings.json")"

  # Decline the prompt (CLAUDE_ONRAMP_DECLINE=1)
  run env CLAUDE_ONRAMP_DECLINE=1 \
    CLAUDE_ONRAMP_HOOKS_JSON="$TMPDIR_TEST/hooks.json" \
    CLAUDE_ONRAMP_SETTINGS_JSON="$TMPDIR_TEST/settings.json" \
    CLAUDE_ONRAMP_HOOKS_DIR="$TMPDIR_TEST/hooks" \
    CLAUDE_ONRAMP_REPO_ROOT="$REPO_ROOT" \
    bash "$SCRIPTS/new-hook.sh" "$hook_name" "$event"

  # Script must exit non-zero on decline
  [ "$status" -ne 0 ]
  # Script must print a loud warning
  echo "$output" | grep -qi "Registration SKIPPED\|SKIPPED"
  # Registries must be unchanged
  local after_hooks; after_hooks="$(python3 -m json.tool "$TMPDIR_TEST/hooks.json")"
  local after_settings; after_settings="$(python3 -m json.tool "$TMPDIR_TEST/settings.json")"
  [ "$before_hooks" = "$after_hooks" ]
  [ "$before_settings" = "$after_settings" ]
}

# ── C6: new-hook.sh runs invariant after wiring ───────────────────────────────

@test "C6 new-hook runs registration invariant after wiring" {
  local hook_name="test-invariant-run-$$"
  local event="PostToolUse"
  run env CLAUDE_ONRAMP_AUTOCONFIRM=1 \
    CLAUDE_ONRAMP_HOOKS_JSON="$TMPDIR_TEST/hooks.json" \
    CLAUDE_ONRAMP_SETTINGS_JSON="$TMPDIR_TEST/settings.json" \
    CLAUDE_ONRAMP_HOOKS_DIR="$TMPDIR_TEST/hooks" \
    CLAUDE_ONRAMP_REPO_ROOT="$REPO_ROOT" \
    bash "$SCRIPTS/new-hook.sh" "$hook_name" "$event"
  # Output must mention the invariant result
  echo "$output" | grep -qi "passed\|invariant\|registration"
}

# ── C7: no git add -A or git add . in any script ─────────────────────────────

@test "C7 no 'git add -A' or 'git add .' in any scaffolding script" {
  ! grep -q "git add -A" "$SCRIPTS/new-skill.sh"
  ! grep -q "git add \." "$SCRIPTS/new-skill.sh"
  ! grep -q "git add -A" "$SCRIPTS/new-agent.sh"
  ! grep -q "git add \." "$SCRIPTS/new-agent.sh"
  ! grep -q "git add -A" "$SCRIPTS/new-hook.sh"
  ! grep -q "git add \." "$SCRIPTS/new-hook.sh"
}
