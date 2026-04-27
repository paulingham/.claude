#!/usr/bin/env bash
# Local-disk adapter. Operates on ~/.claude/session-memory/{hash}/{session_id}.md.
# Functions: session_store_put|get|delete|list|list_subkeys (≤ 5 lines each).

_local_path() { printf '%s\n' "$HOME/.claude/session-memory/$1/$2.md"; }
_local_dir()  { printf '%s\n' "$HOME/.claude/session-memory/$1"; }

_local_put() {
  local dest; dest=$(_local_path "$1" "$2")
  mkdir -p "$(dirname "$dest")" 2>/dev/null || return 1
  [[ "$3" = "-" ]] && { (umask 077 && cat > "$dest"); return; }
  (umask 077 && cp "$3" "$dest")
}

_local_get() {
  local src; src=$(_local_path "$1" "$2")
  [[ -f "$src" ]] || return 1
  cat "$src"
}

_local_delete() {
  local target; target=$(_local_path "$1" "$2")
  rm -f "$target"
}

_local_list() {
  local root="$HOME/.claude/session-memory"
  [[ -d "$root" ]] || return 0
  ( cd "$root" && find . -maxdepth 1 -mindepth 1 -type d | sed 's|^\./||' | sort )
}

_local_list_subkeys() {
  local src; src=$(_local_path "$1" "$2")
  [[ -f "$src" ]] || return 1
  awk '/^# / { sub(/^# /, ""); print }' "$src"
}
