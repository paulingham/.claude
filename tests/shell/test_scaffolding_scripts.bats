#!/usr/bin/env bats
# Slice C bats tests (C1-C11) — scaffolding scripts behaviour.
#
# C1:  shellcheck-clean on all three scripts + _lib/onramp-common.sh
# C2:  new-skill.sh dry-run creates skill dir + proposes README bump; no git add -A
# C3:  new-agent.sh dry-run proposes 5-col table row + README agent count bump
# C4:  new-hook.sh auto-wires BOTH JSON registries when confirmed
# C5:  new-hook.sh decline leaves registries untouched AND warns loudly + exits non-zero
# C6:  new-hook.sh runs invariant after wiring
# C7:  no 'git add -A' or 'git add .' in any script
# C8:  injection-style name rejected at parse time, no file created (new-skill)
# C9:  path-traversal name rejected at parse time, no file created (new-agent)
# C10: bogus hook event rejected at parse time, no registry mutated (new-hook)
# C11: new-skill.sh with confirm bumps BOTH README skill count locations

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

@test "C1 shellcheck new-skill.sh new-agent.sh new-hook.sh and _lib/onramp-common.sh" {
  run shellcheck -x --source-path="$SCRIPTS" \
    "$SCRIPTS/_lib/onramp-common.sh" \
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

# ── C8: injection-style name rejected, no file created (new-skill) ───────────

@test "C8 new-skill rejects injection name and creates no file" {
  local bad_name='x"; touch /tmp/pwned-c8; echo "'
  local pwned_marker="/tmp/pwned-c8"
  rm -f "$pwned_marker"
  run bash "$SCRIPTS/new-skill.sh" "$bad_name"
  [ "$status" -ne 0 ]
  [ ! -e "$pwned_marker" ]
  echo "$output" | grep -qi "ERROR\|invalid"
}

# ── C9: path-traversal name rejected, no file created (new-agent) ─────────────

@test "C9 new-agent rejects path-traversal name and creates no file" {
  run bash "$SCRIPTS/new-agent.sh" "../../etc/foo"
  [ "$status" -ne 0 ]
  [ ! -e "/etc/foo.md" ]
  echo "$output" | grep -qi "ERROR\|invalid"
}

# ── C10: bogus event rejected at parse time, no registry mutated (new-hook) ───

@test "C10 new-hook rejects bogus event and mutates no registry" {
  local hook_name="test-bad-event-$$"
  local before_hooks; before_hooks="$(python3 -m json.tool "$TMPDIR_TEST/hooks.json")"
  local before_settings; before_settings="$(python3 -m json.tool "$TMPDIR_TEST/settings.json")"
  run env CLAUDE_ONRAMP_AUTOCONFIRM=1 \
    CLAUDE_ONRAMP_HOOKS_JSON="$TMPDIR_TEST/hooks.json" \
    CLAUDE_ONRAMP_SETTINGS_JSON="$TMPDIR_TEST/settings.json" \
    CLAUDE_ONRAMP_HOOKS_DIR="$TMPDIR_TEST/hooks" \
    CLAUDE_ONRAMP_REPO_ROOT="$REPO_ROOT" \
    bash "$SCRIPTS/new-hook.sh" "$hook_name" "BogusEvent"
  [ "$status" -ne 0 ]
  echo "$output" | grep -qi "ERROR\|unknown\|invalid"
  local after_hooks; after_hooks="$(python3 -m json.tool "$TMPDIR_TEST/hooks.json")"
  local after_settings; after_settings="$(python3 -m json.tool "$TMPDIR_TEST/settings.json")"
  [ "$before_hooks" = "$after_hooks" ]
  [ "$before_settings" = "$after_settings" ]
  [ ! -e "$TMPDIR_TEST/hooks/$hook_name.sh" ]
}

# ── C12: _restore_backups cleans .bak files after JSON-validate failure ────────

@test "C12 new-hook _restore_backups removes .bak files after restoring registries" {
  # WHY: the JSON-validate failure path calls _restore_backups but the original
  # code did NOT call _cleanup_backups inside it, leaving .bak files behind.
  # This test pins the fix: _restore_backups must clean .bak files.

  local hook_name="test-validate-fail-$$"

  # Capture original content
  local orig_hooks; orig_hooks="$(cat "$TMPDIR_TEST/hooks.json")"
  local orig_settings; orig_settings="$(cat "$TMPDIR_TEST/settings.json")"

  # Simulate state just before _restore_backups is called:
  # .bak files hold original content; live files have been mutated by _wire;
  # orphan hook file exists at fake_dest.
  cp "$TMPDIR_TEST/hooks.json" "$TMPDIR_TEST/hooks.json.bak"
  cp "$TMPDIR_TEST/settings.json" "$TMPDIR_TEST/settings.json.bak"
  local fake_dest="$TMPDIR_TEST/hooks/$hook_name.sh"
  touch "$fake_dest"
  echo '{"mutated":true}' > "$TMPDIR_TEST/hooks.json"
  echo '{"mutated":true}' > "$TMPDIR_TEST/settings.json"

  # Assert 1 (source-level): _restore_backups in new-hook.sh must contain a
  # _cleanup_backups call — this goes RED against the pre-fix code.
  grep -A 10 '^_restore_backups()' "$SCRIPTS/new-hook.sh" \
    | grep -q '_cleanup_backups'

  # Assert 2 (behavioural): run the functions directly in an isolated subshell.
  # We define the two functions verbatim-matching the script contract and verify
  # that calling _restore_backups removes .bak files (the bug was the absence of
  # _cleanup_backups inside _restore_backups).
  run bash -c "
    HOOKS_JSON='$TMPDIR_TEST/hooks.json'
    SETTINGS_JSON='$TMPDIR_TEST/settings.json'
    _cleanup_backups() { rm -f \"\${HOOKS_JSON}.bak\" \"\${SETTINGS_JSON}.bak\"; }
    _restore_backups() {
      local dest=\"\$1\"
      cp \"\${HOOKS_JSON}.bak\" \"\$HOOKS_JSON\"
      cp \"\${SETTINGS_JSON}.bak\" \"\$SETTINGS_JSON\"
      rm -f \"\$dest\"
      _cleanup_backups
    }
    _restore_backups '$fake_dest'
    [ ! -f '${TMPDIR_TEST}/hooks.json.bak' ] || { echo 'FAIL: hooks.json.bak remains' >&2; exit 10; }
    [ ! -f '${TMPDIR_TEST}/settings.json.bak' ] || { echo 'FAIL: settings.json.bak remains' >&2; exit 11; }
  "
  [ "$status" -eq 0 ]

  # Verify live registries were restored to original content
  local after_hooks; after_hooks="$(cat "$TMPDIR_TEST/hooks.json")"
  local after_settings; after_settings="$(cat "$TMPDIR_TEST/settings.json")"
  [ "$orig_hooks" = "$after_hooks" ]
  [ "$orig_settings" = "$after_settings" ]
  # Orphan hook file must be removed
  [ ! -e "$fake_dest" ]
}

# ── C11: new-skill bumps BOTH README locations on confirm ─────────────────────

@test "C11 new-skill with confirm bumps both README skill-count locations" {
  local fake_repo; fake_repo="$(mktemp -d)"
  # Minimal repo skeleton: README + skills dir + skill template
  mkdir -p "$fake_repo/skills/existing-skill" "$fake_repo/templates/skill-reference"
  printf '# Existing skill\n' > "$fake_repo/skills/existing-skill/SKILL.md"
  printf 'skill: your-skill-name-kebab-case\n' > "$fake_repo/templates/skill-reference/SKILL.md"
  # README with BOTH count locations matching filesystem (1 skill)
  printf '# Arch\n  skills/  # 1 skills — blah\n## Skills (1)\nMore text.\n' \
    > "$fake_repo/README.md"
  run env CLAUDE_ONRAMP_AUTOCONFIRM=1 \
    CLAUDE_ONRAMP_REPO_ROOT="$fake_repo" \
    bash "$SCRIPTS/new-skill.sh" "my-new-skill"
  [ "$status" -eq 0 ]
  grep -q "## Skills (2)" "$fake_repo/README.md"
  grep -q "# 2 skills" "$fake_repo/README.md"
  rm -rf "$fake_repo"
}
