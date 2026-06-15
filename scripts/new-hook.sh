#!/usr/bin/env bash
# new-hook.sh — scaffold a new hook under hooks/<name>.sh and wire BOTH registries.
# Usage: new-hook.sh <hook-name> <Event>
# WHY: hooks require DUAL registration in hooks/hooks.json AND settings.json;
#      missing either means the hook silently never fires in some contexts.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${CLAUDE_ONRAMP_REPO_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
# shellcheck source=_lib/onramp-common.sh
source "$SCRIPT_DIR/_lib/onramp-common.sh"

TEMPLATE="$REPO_ROOT/templates/hook-template.sh"
HOOKS_JSON="${CLAUDE_ONRAMP_HOOKS_JSON:-$REPO_ROOT/hooks/hooks.json}"
SETTINGS_JSON="${CLAUDE_ONRAMP_SETTINGS_JSON:-$REPO_ROOT/settings.json}"
HOOKS_DIR="${CLAUDE_ONRAMP_HOOKS_DIR:-$REPO_ROOT/hooks}"
HOOK_NAME=""
EVENT=""

_usage() {
  echo "Usage: $0 <hook-name-kebab-case> <Event>" >&2
  echo "  Valid events: ${_OC_VALID_EVENTS[*]}" >&2
  exit 1
}

_parse_args() {
  case "${1:-}" in --help|-h) _usage ;; esac
  [[ $# -eq 2 ]] || _usage
  HOOK_NAME="$1"
  EVENT="$2"
  _oc_validate_name "$HOOK_NAME"
  _oc_validate_event "$EVENT"
}

_idiom_command() {
  echo "h=\"\${CLAUDE_PLUGIN_ROOT:-\${CLAUDE_CONFIG_DIR:-\$HOME/.claude}}/hooks/${HOOK_NAME}.sh\"; [ -x \"\$h\" ] && exec \"\$h\" || exit 0"
}

_print_proposed_diff() {
  local dest="$1"
  echo "=== Proposed changes ==="
  echo "  CREATE $dest"
  echo "  UPDATE $HOOKS_JSON: add $HOOK_NAME under $EVENT"
  echo "  UPDATE $SETTINGS_JSON: add $HOOK_NAME under $EVENT"
  echo ""
  echo "  Registration idiom:"
  printf '    %s\n' "$(_idiom_command)"
}

_backup() {
  cp "$HOOKS_JSON" "${HOOKS_JSON}.bak"
  cp "$SETTINGS_JSON" "${SETTINGS_JSON}.bak"
}

_restore_backups() {
  local dest="$1"
  cp "${HOOKS_JSON}.bak" "$HOOKS_JSON"
  cp "${SETTINGS_JSON}.bak" "$SETTINGS_JSON"
  rm -f "$dest"
  _cleanup_backups
}

_cleanup_backups() {
  rm -f "${HOOKS_JSON}.bak" "${SETTINGS_JSON}.bak"
}

_validate_json() {
  python3 -m json.tool "$HOOKS_JSON" > /dev/null 2>&1 \
    && python3 -m json.tool "$SETTINGS_JSON" > /dev/null 2>&1
}

_wire_both_registries() {
  local idiom; idiom="$(_idiom_command)"
  python3 - "$HOOKS_JSON" "$SETTINGS_JSON" "$EVENT" "$idiom" <<'PYEOF'
import json, sys

hooks_path, settings_path, event, idiom = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
entry = {"type": "command", "command": "bash", "args": ["-lc", idiom], "timeout": 10000}

def append_hook_entry(path, ev, ent):
    with open(path) as f:
        data = json.load(f)
    blocks = data.setdefault("hooks", {}).setdefault(ev, [])
    if not blocks:
        blocks.append({"hooks": []})
    blocks[0].setdefault("hooks", []).append(ent)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")

append_hook_entry(hooks_path, event, entry)
append_hook_entry(settings_path, event, entry)
PYEOF
}

_create_hook_file() {
  local dest="$1"
  sed "s/your-hook-name/$HOOK_NAME/g" "$TEMPLATE" > "$dest"
  chmod +x "$dest"
  echo "  Created: $dest"
}

_run_invariant() {
  echo ""
  echo "--- Running registration invariant ---"
  if bash "$REPO_ROOT/hooks/tests/test-hook-registration-invariant.sh" 2>&1; then
    echo "--- Invariant: PASSED ---"
  else
    echo "--- Invariant: FAILED (check output above) ---"
  fi
}

main() {
  _parse_args "$@"
  local dest="$HOOKS_DIR/$HOOK_NAME.sh"
  [[ -e "$dest" ]] && { echo "hook already exists: $dest" >&2; exit 1; }
  _print_proposed_diff "$dest"
  if ! _oc_confirm; then
    echo ""
    echo "WARNING: Registration SKIPPED — $HOOKS_DIR/$HOOK_NAME.sh is NOT wired." >&2
    echo "Re-run scripts/new-hook.sh $HOOK_NAME $EVENT and confirm to register" >&2
    echo "it in hooks.json + settings.json." >&2
    exit 1
  fi
  _backup
  _create_hook_file "$dest"
  _wire_both_registries
  if ! _validate_json; then
    echo "ERROR: registry JSON invalid after write — restoring backups" >&2
    _restore_backups "$dest"
    exit 1
  fi
  _cleanup_backups
  echo "  Updated: $HOOKS_JSON"
  echo "  Updated: $SETTINGS_JSON"
  _run_invariant
}

main "$@"
