#!/usr/bin/env bats
# cloud-link.sh — symlink a harness checkout into $HOME/.claude.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  LIB="$REPO_ROOT/scripts/_lib/cloud-link.sh"
  TMP="$(mktemp -d -t cl.XXXXXX)"
  SRC="$TMP/project"
  DST="$TMP/home/.claude"
  mkdir -p "$SRC" "$DST"

  # Minimal harness fixture in SRC: enough to satisfy cloud_link_should_run
  # plus a representative file, dir, and missing item.
  : > "$SRC/CLAUDE.md"
  : > "$SRC/settings.json"
  mkdir -p "$SRC/skills/intake"
  : > "$SRC/skills/intake/SKILL.md"
  mkdir -p "$SRC/hooks"
  : > "$SRC/hooks/example.sh"

  # shellcheck source=../../scripts/_lib/cloud-link.sh
  . "$LIB"
}

teardown() {
  [ -d "$TMP" ] && rm -rf "$TMP"
}

@test "should_run: false when CLAUDE_CODE_REMOTE unset" {
  unset CLAUDE_CODE_REMOTE
  CLAUDE_PROJECT_DIR="$SRC" HOME="$TMP/home" run cloud_link_should_run
  [ "$status" -ne 0 ]
}

@test "should_run: false when source has no harness markers" {
  rm -f "$SRC/CLAUDE.md"
  CLAUDE_CODE_REMOTE=true CLAUDE_PROJECT_DIR="$SRC" HOME="$TMP/home" run cloud_link_should_run
  [ "$status" -ne 0 ]
}

@test "should_run: false when src and dst resolve to same path" {
  CLAUDE_CODE_REMOTE=true CLAUDE_PROJECT_DIR="$SRC" HOME="$SRC/.." run bash -c '
    . "'"$LIB"'"
    mkdir -p "$HOME/.claude"
    rmdir "$HOME/.claude"
    ln -s "'"$SRC"'" "$HOME/.claude"
    cloud_link_should_run
  '
  [ "$status" -ne 0 ]
}

@test "should_run: true on a clean cloud env" {
  CLAUDE_CODE_REMOTE=true CLAUDE_PROJECT_DIR="$SRC" HOME="$TMP/home" run cloud_link_should_run
  [ "$status" -eq 0 ]
}

@test "harness: links files and dirs from src into dst" {
  HOME="$TMP/home" run cloud_link_harness "$SRC" "$DST"
  [ "$status" -eq 0 ]
  [ -L "$DST/CLAUDE.md" ]
  [ -L "$DST/settings.json" ]
  [ -L "$DST/skills" ]
  [ -L "$DST/hooks" ]
  [ "$(readlink "$DST/skills")" = "$SRC/skills" ]
  # File visible through the symlink
  [ -f "$DST/skills/intake/SKILL.md" ]
}

@test "harness: idempotent — second run is all 'already linked'" {
  HOME="$TMP/home" cloud_link_harness "$SRC" "$DST" >/dev/null
  HOME="$TMP/home" run cloud_link_harness "$SRC" "$DST"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q "already linked"
  ! echo "$output" | grep -q "backed up"
}

@test "harness: backs up pre-existing non-symlink entries" {
  mkdir -p "$DST/skills/session-start-hook"
  echo "marketplace" > "$DST/skills/session-start-hook/SKILL.md"
  echo "stub" > "$DST/settings.json"

  HOME="$TMP/home" run cloud_link_harness "$SRC" "$DST"
  [ "$status" -eq 0 ]
  [ -L "$DST/skills" ]
  [ -L "$DST/settings.json" ]

  # Backup contains the pre-existing entries
  backup_dir="$(find "$DST/.cloud-link-backup" -mindepth 1 -maxdepth 1 -type d | head -1)"
  [ -d "$backup_dir/skills" ]
  [ -f "$backup_dir/skills/session-start-hook/SKILL.md" ]
  [ -f "$backup_dir/settings.json" ]
  grep -q stub "$backup_dir/settings.json"
}

@test "harness: skips items absent from source" {
  # MEMORY.md is in the link list but not in the fixture
  HOME="$TMP/home" run cloud_link_harness "$SRC" "$DST"
  [ "$status" -eq 0 ]
  [ ! -e "$DST/MEMORY.md" ]
  echo "$output" | grep -q "skip  MEMORY.md"
}

@test "harness: returns 1 when source dir missing" {
  HOME="$TMP/home" run cloud_link_harness "$TMP/nope" "$DST"
  [ "$status" -ne 0 ]
}
