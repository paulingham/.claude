#!/usr/bin/env bash
# Claude Code harness bootstrap — fetched by the managed-settings SessionStart hook.
# Clones or updates ~/.claude/ from the Adviser-Group GitHub repo.
# MUST exit 0 on every path so a failed bootstrap never blocks Claude Code from starting.

set +e
umask 077

REPO_HTTPS="https://github.com/Adviser-Group/.claude.git"
REPO_SLUG="Adviser-Group/.claude"
TARGET="$HOME/.claude"
STAMP="$TARGET/.harness-last-check"
LOG="$TARGET/.bootstrap.log"
TODAY="$(date -u +%Y-%m-%d)"

log() {
  mkdir -p "$TARGET" 2>/dev/null
  printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" >> "$LOG" 2>/dev/null
}

trim_log() {
  [ -f "$LOG" ] || return 0
  tail -n 200 "$LOG" > "$LOG.tmp" 2>/dev/null && mv "$LOG.tmp" "$LOG" 2>/dev/null
}

clone_cmd() {
  if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    gh repo clone "$REPO_SLUG" "$1" -- --depth=1
  else
    git clone --depth=1 "$REPO_HTTPS" "$1"
  fi
}

if [ -f "$STAMP" ] && [ "$(cat "$STAMP" 2>/dev/null)" = "$TODAY" ]; then
  exit 0
fi

if [ ! -d "$TARGET/.git" ]; then
  log "no git repo at $TARGET — performing fresh clone"
  if [ -e "$TARGET" ]; then
    BACKUP="$HOME/.claude.bak.$(date -u +%Y%m%dT%H%M%SZ)"
    mv "$TARGET" "$BACKUP" 2>/dev/null
    log "existing $TARGET moved to $BACKUP"
  fi
  TMP="$HOME/.claude.new.$$"
  if clone_cmd "$TMP" >>"$LOG" 2>&1; then
    mv "$TMP" "$TARGET" 2>/dev/null
    log "clone OK"
  else
    log "clone FAILED — leaving previous state untouched"
    rm -rf "$TMP" 2>/dev/null
    exit 0
  fi
else
  log "pulling latest"
  git -C "$TARGET" fetch --depth=1 origin >>"$LOG" 2>&1
  git -C "$TARGET" reset --hard "@{u}" >>"$LOG" 2>&1
fi

find "$TARGET/hooks" -type f -name '*.sh' -exec chmod +x {} \; 2>/dev/null
find "$TARGET/scripts" -type f \( -name '*.sh' -o -name '*.py' \) -exec chmod +x {} \; 2>/dev/null

for d in memory learning pipeline-state session-memory agent-memory metrics db; do
  mkdir -p "$TARGET/$d" 2>/dev/null
done

printf '%s' "$TODAY" > "$STAMP"
log "bootstrap complete (commit $(git -C "$TARGET" rev-parse --short HEAD 2>/dev/null))"
trim_log
exit 0
