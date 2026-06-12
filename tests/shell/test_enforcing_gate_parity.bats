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
