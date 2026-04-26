#!/usr/bin/env bash
# Register, list, and clean up worktree-scoped scratch tools for /tool-synthesis.
#
# Usage:
#   register.sh <tool-name> <source-path> [description]
#   register.sh --list [worktree-dir]
#   register.sh --cleanup [worktree-dir]
#
# Tools are copied into ${WORKTREE}/.claude-scratch-tools/<tool-name>, marked
# executable, and recorded in registry.json. The directory is self-gitignored.
# Per-worktree by construction — each worktree has its own scratch dir.
set -euo pipefail

SCRATCH_DIR_NAME=".claude-scratch-tools"
SAFE_NAME_RE='^[a-zA-Z0-9][a-zA-Z0-9._-]*$'

scratch_dir_for() {
  printf '%s/%s\n' "${1:-$PWD}" "$SCRATCH_DIR_NAME"
}

ensure_dir() {
  local dir="$1"
  mkdir -p "$dir"
  [ -f "$dir/.gitignore" ] || printf '*\n!.gitignore\n!registry.json\n' > "$dir/.gitignore"
  [ -f "$dir/registry.json" ] || printf '{"tools": []}\n' > "$dir/registry.json"
}

is_registered() {
  grep -q "\"name\": \"$1\"" "$2" 2>/dev/null
}

append_registry_entry() {
  local name="$1" desc="$2" registry="$3" tmp
  tmp="$(mktemp)"
  python3 - "$registry" "$name" "$desc" "$tmp" <<'PY'
import json, sys
registry, name, desc, tmp = sys.argv[1:5]
data = json.load(open(registry))
data["tools"].append({"name": name, "description": desc})
json.dump(data, open(tmp, "w"), indent=2)
PY
  mv "$tmp" "$registry"
}

cmd_register() {
  local name="$1" src="$2" desc="${3:-}"
  [[ "$name" =~ $SAFE_NAME_RE ]] || { echo "register: unsafe tool name '$name'" >&2; return 2; }
  [ -f "$src" ] || { echo "register: source '$src' not found" >&2; return 2; }
  local dir registry dest
  dir="$(scratch_dir_for)"
  ensure_dir "$dir"
  registry="$dir/registry.json"
  dest="$dir/$name"
  cp "$src" "$dest"
  chmod +x "$dest"
  if ! is_registered "$name" "$registry"; then
    append_registry_entry "$name" "$desc" "$registry"
  fi
  printf 'Registered %s at %s\n' "$name" "$dest"
}

cmd_list() {
  local dir registry
  dir="$(scratch_dir_for "$1")"
  registry="$dir/registry.json"
  [ -f "$registry" ] || { echo "(no scratch tools registered)"; return 0; }
  python3 -c 'import json,sys
for t in json.load(open(sys.argv[1]))["tools"]:
    print("  - {}: {}".format(t["name"], t["description"]))' "$registry"
}

cmd_cleanup() {
  local dir
  dir="$(scratch_dir_for "$1")"
  [ -d "$dir" ] && rm -rf "$dir" && echo "Cleaned $dir" || echo "(nothing to clean)"
}

main() {
  case "${1:-}" in
    --list) shift; cmd_list "${1:-$PWD}" ;;
    --cleanup) shift; cmd_cleanup "${1:-$PWD}" ;;
    -h|--help|"") echo "Usage: register.sh <name> <src> [desc] | --list [dir] | --cleanup [dir]"; exit 0 ;;
    *) cmd_register "$@" ;;
  esac
}

main "$@"
