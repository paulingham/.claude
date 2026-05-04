#!/usr/bin/env bash
# cloud-link.sh — link a harness checkout into $HOME/.claude.
#
# On Claude Code on the web, the platform clones this repo into the workspace
# (e.g. /home/user/.claude) but Claude Code's loader reads skills/agents/hooks
# from $HOME/.claude (e.g. /root/.claude). This library reconciles the two by
# symlinking each harness artifact from the project checkout into $HOME/.claude.
#
# Idempotent. Safe to re-run. Pre-existing non-symlink entries at the target are
# moved into $claude_home/.cloud-link-backup/<timestamp>/ before the symlink is
# created, so nothing is destroyed silently.
#
# Public API:
#   cloud_link_should_run            — exit 0 if cloud-link is applicable
#   cloud_link_harness <src> <dst>   — perform the linking; returns 0 on success
#
# Both functions are pure-ish: they print a one-line summary per artifact to
# stdout and never write to stderr unless something genuinely failed. Tests
# capture stdout to assert behaviour.

# Files at the top level of the harness that should be linked into $HOME/.claude.
# Listed explicitly (not auto-discovered) so future runtime artifacts at the
# project root are NOT linked accidentally.
_CLOUD_LINK_FILES=(
  "CLAUDE.md"
  "README.md"
  "MEMORY.md"
  "settings.json"
  "setup.sh"
  "statusline-command.sh"
  "statusline-robbyrussell.sh"
)

_CLOUD_LINK_DIRS=(
  "agent-memory"
  "agents"
  "automation"
  "db"
  "eval"
  "hooks"
  "knowledge"
  "memory"
  "orchestrator"
  "pipeline-state"
  "rules"
  "scripts"
  "session-memory"
  "skills"
  "tests"
)

_cloud_link_resolve() {
  if command -v realpath >/dev/null 2>&1; then
    realpath "$1" 2>/dev/null && return
  fi
  (cd "$1" 2>/dev/null && pwd -P) || printf '%s' "$1"
}

# cloud_link_should_run
# Exit 0 when:
#   - CLAUDE_CODE_REMOTE=true (we're on a cloud session), AND
#   - CLAUDE_PROJECT_DIR is set and looks like a harness checkout, AND
#   - $HOME/.claude is NOT already the same path as $CLAUDE_PROJECT_DIR.
# Exit 1 otherwise.
cloud_link_should_run() {
  [ "${CLAUDE_CODE_REMOTE:-}" = "true" ] || return 1
  [ -n "${CLAUDE_PROJECT_DIR:-}" ] || return 1
  [ -f "$CLAUDE_PROJECT_DIR/CLAUDE.md" ] || return 1
  [ -d "$CLAUDE_PROJECT_DIR/skills/intake" ] || return 1
  local src dst
  src="$(_cloud_link_resolve "$CLAUDE_PROJECT_DIR")"
  dst="$(_cloud_link_resolve "$HOME/.claude" 2>/dev/null || printf '%s' "$HOME/.claude")"
  [ "$src" != "$dst" ]
}

# _cloud_link_one <src_path> <dst_path> <backup_dir>
# Link src to dst. If dst exists and is not already a symlink to src, move it
# to backup_dir/$(basename dst) first.
_cloud_link_one() {
  local src="$1" dst="$2" backup_dir="$3"

  if [ ! -e "$src" ]; then
    printf 'skip  %s (not in source)\n' "$(basename "$dst")"
    return 0
  fi

  if [ -L "$dst" ]; then
    local current
    current="$(readlink "$dst")"
    if [ "$current" = "$src" ]; then
      printf 'ok    %s (already linked)\n' "$(basename "$dst")"
      return 0
    fi
  fi

  if [ -e "$dst" ] || [ -L "$dst" ]; then
    mkdir -p "$backup_dir"
    mv "$dst" "$backup_dir/$(basename "$dst")" || return 1
  fi

  ln -s "$src" "$dst" || return 1
  printf 'link  %s\n' "$(basename "$dst")"
}

# cloud_link_harness <src> <dst>
# src: harness checkout path (e.g. $CLAUDE_PROJECT_DIR)
# dst: $HOME/.claude
cloud_link_harness() {
  local src="$1" dst="$2"
  local timestamp backup_dir item

  [ -d "$src" ] || { printf 'cloud-link: source %s missing\n' "$src" >&2; return 1; }

  mkdir -p "$dst" || return 1

  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  backup_dir="$dst/.cloud-link-backup/$timestamp"

  for item in "${_CLOUD_LINK_FILES[@]}"; do
    _cloud_link_one "$src/$item" "$dst/$item" "$backup_dir" || return 1
  done

  for item in "${_CLOUD_LINK_DIRS[@]}"; do
    _cloud_link_one "$src/$item" "$dst/$item" "$backup_dir" || return 1
  done

  if [ -d "$backup_dir" ]; then
    printf 'cloud-link: backed up pre-existing entries to %s\n' "$backup_dir"
  fi
}
