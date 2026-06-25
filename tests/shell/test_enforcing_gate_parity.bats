#!/usr/bin/env bats
# AC-C4: enforcing-gate parity — settings.json ENFORCING hooks must also be in hooks.json
# WHY: plugin installs only load hooks.json; a hook absent from hooks.json is silently bypassed
#      on plugin install paths, even if settings.json wires it for direct-install users.

REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/../.." && pwd)"
HOOKS_JSON="$REPO_ROOT/hooks/hooks.json"
SETTINGS_JSON="$REPO_ROOT/settings.json"
HOOKS_DIR="$REPO_ROOT/hooks"

# --------------------------------------------------------------------------
# AC-C4.1: the 4 ported basenames must be present in hooks/hooks.json
# --------------------------------------------------------------------------

@test "AC-C4.1a: intake-backstop.sh is registered in hooks.json" {
  grep -q "intake-backstop" "$HOOKS_JSON"
}

@test "AC-C4.1b: pytest-suite-guard.sh is registered in hooks.json" {
  grep -q "pytest-suite-guard" "$HOOKS_JSON"
}

@test "AC-C4.1c: syntax-check.sh is registered in hooks.json" {
  grep -q "syntax-check" "$HOOKS_JSON"
}

@test "AC-C4.1d: build-loop-scan.sh is registered in hooks.json" {
  grep -q "build-loop-scan" "$HOOKS_JSON"
}

# --------------------------------------------------------------------------
# AC-C4.2: the 3 live-only-intentional basenames must NOT be in hooks.json
# WHY: these are advisory gates that rely on live-session context unavailable
#      to plugin installs — porting them would break plugin install sessions.
# --------------------------------------------------------------------------

@test "AC-C4.2a: pre-agent-over-spawn-guard.sh NOT in hooks.json (live-only)" {
  ! grep -q "pre-agent-over-spawn-guard" "$HOOKS_JSON"
}

@test "AC-C4.2b: pre-agent-swe-pruner.sh NOT in hooks.json (live-only)" {
  ! grep -q "pre-agent-swe-pruner" "$HOOKS_JSON"
}

@test "AC-C4.2c: stuck-guard.sh NOT in hooks.json (live-only)" {
  ! grep -q "stuck-guard" "$HOOKS_JSON"
}

# --------------------------------------------------------------------------
# AC-C4.3: drift-prevention — every settings.json hook with reachable exit 2
#          (body OR sourced _lib) must be in hooks.json OR on the live-only allowlist.
#
# The detector follows one level of source _lib/*.sh to catch lib-delegated exit 2.
# KNOWN-POSITIVE FIXTURE: runtime-guard.sh exits 2 via _lib/runtime-guard-dispatch.sh;
#   the test asserts our detector finds it, proving the lib-follow logic works.
# --------------------------------------------------------------------------

# Helper: extract hook basenames registered in settings.json
_settings_hook_basenames() {
  command -v python3 > /dev/null 2>&1 || skip "python3 required for parity check"
  python3 - "$SETTINGS_JSON" <<'PYEOF'
import json, sys, re

with open(sys.argv[1]) as f:
    data = json.load(f)

hooks_section = data.get("hooks", {})
basenames = set()
for event_hooks in hooks_section.values():
    for block in event_hooks:
        for hook in block.get("hooks", []):
            args = hook.get("args", [])
            for arg in args:
                m = re.search(r'/hooks/([^/"]+\.sh)', arg)
                if m:
                    basenames.add(m.group(1))
print("\n".join(sorted(basenames)))
PYEOF
}

# Helper: does a hook script (or its sourced _lib scripts) contain exit 2 or return 2?
# NOTE: follows ONE level of `source _lib/*.sh`; deeper delegation (lib-A -> lib-B) is
# not detected. Verified zero such multi-level delegates exist today — documented boundary.
_hook_is_enforcing() {
  local script="$HOOKS_DIR/$1"
  [ -f "$script" ] || return 1

  # Direct exit 2 in the script body
  if grep -qE 'exit 2|return 2' "$script"; then
    return 0
  fi

  # Follow one level of sourced _lib scripts
  local lib_name
  while IFS= read -r lib_name; do
    local lib_path="$HOOKS_DIR/_lib/$lib_name"
    if [ -f "$lib_path" ] && grep -qE 'exit 2|return 2' "$lib_path"; then
      return 0
    fi
  done < <(grep -oE '_lib/[A-Za-z0-9_-]+\.sh' "$script" | sed 's|_lib/||')

  return 1
}

# Live-only exemption allowlist — intentionally excluded from hooks.json.
# WHY: these advisory hooks block via permissionDecision JSON (or are pure exit-0
# advisory), NOT exit 2 — so _hook_is_enforcing never flags them; this allowlist is
# defensive (keeps the parity test correct if one ever gains a lib-level exit 2).
_is_live_only_exempt() {
  local basename="$1"
  case "$basename" in
    pre-agent-over-spawn-guard.sh|\
    pre-agent-swe-pruner.sh|\
    stuck-guard.sh)
      return 0 ;;
  esac
  return 1
}

@test "AC-C4.3: known-positive fixture — detector finds runtime-guard.sh exit-2-in-lib" {
  # WHY: runtime-guard.sh has NO direct exit 2; it exits 2 only via
  #      _lib/runtime-guard-dispatch.sh. This test proves the lib-follow logic works.
  #      If this fails, the drift-prevention detector is broken.
  run _hook_is_enforcing "runtime-guard.sh"
  [ "$status" -eq 0 ]
}

@test "AC-C4.3: every settings.json enforcing hook is in hooks.json or live-only allowlist" {
  local missing=()

  while IFS= read -r basename; do
    [ -z "$basename" ] && continue

    # Only check hooks that have reachable exit 2
    _hook_is_enforcing "$basename" || continue

    # Exempt live-only advisory hooks
    _is_live_only_exempt "$basename" && continue

    # Must be present in hooks.json
    if ! grep -q "$basename" "$HOOKS_JSON"; then
      missing+=("$basename")
    fi
  done < <(_settings_hook_basenames)

  if [ "${#missing[@]}" -gt 0 ]; then
    echo "ENFORCING hooks in settings.json missing from hooks.json:"
    printf '  %s\n' "${missing[@]}"
    return 1
  fi
}

# --------------------------------------------------------------------------
# AC-D1: REVERSE parity — every ENFORCING (exit 2) hook in hooks.json must
#         also appear in settings.json OR be on the hooks-json-only allowlist.
#
# WHY: settings.json is enforced independently of hooks.json (#18517).
#      An enforcing hook absent from settings.json is silently bypassed on
#      direct-install sessions that load settings.json but not hooks.json.
#      This catches future dual-registration drift like the runtime-state-guard
#      / agentic-security-gate gap closed by this task.
# --------------------------------------------------------------------------

# Helper: extract hook basenames registered in hooks.json
_hooks_json_basenames() {
  python3 - "$HOOKS_JSON" <<'PYEOF'
import json, sys, re

with open(sys.argv[1]) as f:
    data = json.load(f)

basenames = set()
for event_hooks in data.get("hooks", {}).values():
    for block in event_hooks:
        for hook in block.get("hooks", []):
            args = hook.get("args", [])
            for arg in args:
                m = re.search(r'/hooks/([^/"]+\.sh)', arg)
                if m:
                    basenames.add(m.group(1))
print("\n".join(sorted(basenames)))
PYEOF
}

# Hooks-json-only allowlist — enforcing hooks intentionally absent from settings.json.
# WHY: none currently; placeholder so the allowlist pattern is clear for future use.
_is_hooks_json_only_allowlist() {
  local basename="$1"
  case "$basename" in
    __canary-test-hook-never-real__.sh)
      return 0 ;;
  esac
  return 1
}

@test "AC-D1: every hooks.json enforcing hook is in settings.json or hooks-json-only allowlist" {
  local missing=()

  while IFS= read -r basename; do
    [ -z "$basename" ] && continue

    # Only check hooks that have reachable exit 2
    _hook_is_enforcing "$basename" || continue

    # Exempt explicitly-allowlisted hooks-json-only entries
    _is_hooks_json_only_allowlist "$basename" && continue

    # Must be present in settings.json
    if ! grep -q "$basename" "$SETTINGS_JSON"; then
      missing+=("$basename")
    fi
  done < <(_hooks_json_basenames)

  if [ "${#missing[@]}" -gt 0 ]; then
    echo "ENFORCING hooks in hooks.json missing from settings.json:"
    printf '  %s\n' "${missing[@]}"
    return 1
  fi
}

# --------------------------------------------------------------------------
# AC-D2: CANARY — prove the reverse assertion actually bites.
#
# WHY: a canary that never fires is worthless. We inject a synthetic
#      enforcing hook into hooks.json, run the reverse assertion logic
#      directly, and assert it returns non-zero (RED). If the canary
#      itself returns 0, the detector is broken.
# --------------------------------------------------------------------------

@test "AC-D2: canary — synthetic hooks.json-only enforcing hook makes reverse assertion RED" {
  local tmpdir
  tmpdir="$(mktemp -d)"
  local fake_hooks_json="$tmpdir/hooks.json"
  local fake_hook_script="$tmpdir/canary-enforcing-hook.sh"

  # WHY: write a real shell script with exit 2 so _hook_is_enforcing returns 0.
  printf '#!/usr/bin/env bash\nexit 2\n' > "$fake_hook_script"
  chmod +x "$fake_hook_script"

  # Inject the canary basename into a minimal hooks.json fragment
  python3 - "$HOOKS_JSON" "$fake_hooks_json" "canary-enforcing-hook.sh" <<'PYEOF'
import json, sys

with open(sys.argv[1]) as f:
    data = json.load(f)

canary_name = sys.argv[3]
plugin_root = "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}"
canary_entry = {
    "type": "command",
    "command": "bash",
    "args": ["-lc", f'h="{plugin_root}/hooks/{canary_name}"; [ -x "$h" ] && exec "$h" || exit 0'],
    "timeout": 5000
}

data.setdefault("hooks", {}).setdefault("PreToolUse", [])
data["hooks"]["PreToolUse"].append({"matcher": "Bash", "hooks": [canary_entry]})

with open(sys.argv[2], "w") as f:
    json.dump(data, f)
PYEOF

  # Run the reverse assertion against the modified hooks.json and real settings.json.
  # It must return non-zero (RED) because the canary is enforcing but not in settings.json.
  local hooks_dir_saved="$HOOKS_DIR"
  local missing=()

  while IFS= read -r basename; do
    [ -z "$basename" ] && continue

    # Resolve the script path — canary lives in tmpdir, others in HOOKS_DIR
    local script_path
    if [ "$basename" = "canary-enforcing-hook.sh" ]; then
      script_path="$fake_hook_script"
    else
      script_path="$HOOKS_DIR/$basename"
    fi

    # Inline exit-2 check (can't call _hook_is_enforcing with different path)
    local is_enforcing=0
    if [ -f "$script_path" ] && grep -qE 'exit 2|return 2' "$script_path"; then
      is_enforcing=1
    fi
    [ "$is_enforcing" -eq 1 ] || continue

    _is_hooks_json_only_allowlist "$basename" && continue

    if ! grep -q "$basename" "$SETTINGS_JSON"; then
      missing+=("$basename")
    fi
  done < <(python3 - "$fake_hooks_json" <<'PYEOF'
import json, sys, re
with open(sys.argv[1]) as f:
    data = json.load(f)
basenames = set()
for event_hooks in data.get("hooks", {}).values():
    for block in event_hooks:
        for hook in block.get("hooks", []):
            args = hook.get("args", [])
            for arg in args:
                m = re.search(r'/hooks/([^/"]+\.sh)', arg)
                if m:
                    basenames.add(m.group(1))
print("\n".join(sorted(basenames)))
PYEOF
)

  rm -rf "$tmpdir"

  # Canary MUST be in the missing list — if not, the detector is broken
  local found_canary=0
  for m in "${missing[@]}"; do
    [ "$m" = "canary-enforcing-hook.sh" ] && found_canary=1
  done

  if [ "$found_canary" -eq 0 ]; then
    echo "CANARY FAILURE: detector did not catch the synthetic hooks.json-only enforcing hook"
    echo "The reverse-parity assertion (AC-D1) would not have caught this drift."
    return 1
  fi
}
