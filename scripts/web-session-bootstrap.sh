#!/usr/bin/env bash
# Claude Code on the web — sandbox session bootstrap.
#
# Makes a sandbox session use the harness source tree (typically mounted at
# /home/user/.claude) instead of the near-empty runtime config dir at
# /root/.claude. Without this bootstrap, the web sandbox sees ~1 hook and
# ~1 skill registered; after this bootstrap, it sees the full harness.
#
# Usage:
#     bash scripts/web-session-bootstrap.sh           # apply, then verify
#     CLAUDE_SRC=/path/to/.claude bash scripts/web-session-bootstrap.sh
#
# Where to invoke: whatever pre-session env mechanism the sandbox provides
# (a SessionStart hook, container entrypoint, or shell init file). The
# session must restart after this runs — `CLAUDE_CONFIG_DIR` is read at
# session start, mid-session changes don't take effect.
#
# Idempotent: safe to re-run.

set -euo pipefail

# ─────────────────────────────────────────────────────────────────
# Source tree location (override via CLAUDE_SRC=...)
# ─────────────────────────────────────────────────────────────────
CLAUDE_SRC="${CLAUDE_SRC:-/home/user/.claude}"

if [[ ! -d "$CLAUDE_SRC" ]]; then
    echo "ERROR: source tree not found at $CLAUDE_SRC" >&2
    echo "Set CLAUDE_SRC=/path/to/.claude if your sandbox mounts the repo elsewhere." >&2
    exit 1
fi

# ─────────────────────────────────────────────────────────────────
# 1. Config dir — official Claude Code env var (read at session start)
# ─────────────────────────────────────────────────────────────────
export CLAUDE_CONFIG_DIR="$CLAUDE_SRC"

# ─────────────────────────────────────────────────────────────────
# 2. Data-side overrides — make instincts, agent frontmatter, and
#    in-progress pipeline state read from the source tree.
#    These are documented as test-only overrides in the harness, but
#    are the cleanest workaround until CLAUDE_DATA_DIR ships.
# ─────────────────────────────────────────────────────────────────
export CLAUDE_INSTINCTS_DIR="$CLAUDE_SRC/learning"
export CLAUDE_AGENTS_DIR="$CLAUDE_SRC/agents"
export CLAUDE_PIPELINE_STATE_DIR="$CLAUDE_SRC/pipeline-state"

# ─────────────────────────────────────────────────────────────────
# 3. Symlink fallback for code paths that reference $HOME/.claude/…
#    directly (e.g. METRICS_DIR, supervisor.pid, learning observations).
#    Only the SHIPPED dirs are linked; pure-runtime dirs (metrics, db,
#    sessions, state, backups, shell-snapshots) stay in $HOME/.claude.
# ─────────────────────────────────────────────────────────────────
mkdir -p "$HOME/.claude"
SHIPPED_DIRS=(
    hooks skills rules agents knowledge orchestrator scripts
    learning agent-memory session-memory pipeline-state memory
    automation eval CLAUDE.md README.md settings.json
)
for entry in "${SHIPPED_DIRS[@]}"; do
    target="$CLAUDE_SRC/$entry"
    link="$HOME/.claude/$entry"
    [[ -e "$target" ]] || continue
    # Already a correct symlink → skip
    if [[ -L "$link" && "$(readlink "$link")" == "$target" ]]; then
        continue
    fi
    # Real (non-symlink) file/dir → don't clobber
    if [[ -e "$link" && ! -L "$link" ]]; then
        echo "WARN: $link exists and is not a symlink; skipping" >&2
        continue
    fi
    ln -snf "$target" "$link"
done

# ─────────────────────────────────────────────────────────────────
# 4. Verification — fail fast if the sandbox layout is wrong
# ─────────────────────────────────────────────────────────────────
[[ -d "$CLAUDE_CONFIG_DIR/skills" ]]   || { echo "ERROR: $CLAUDE_CONFIG_DIR/skills missing" >&2; exit 1; }
[[ -d "$CLAUDE_CONFIG_DIR/hooks" ]]    || { echo "ERROR: $CLAUDE_CONFIG_DIR/hooks missing"  >&2; exit 1; }
[[ -d "$CLAUDE_CONFIG_DIR/agents" ]]   || { echo "ERROR: $CLAUDE_CONFIG_DIR/agents missing" >&2; exit 1; }
[[ -f "$CLAUDE_CONFIG_DIR/settings.json" ]] || { echo "ERROR: settings.json missing" >&2; exit 1; }

SKILLS_COUNT=$(find "$CLAUDE_CONFIG_DIR/skills" -maxdepth 1 -mindepth 1 -type d | wc -l)
HOOKS_COUNT=$(find "$CLAUDE_CONFIG_DIR/hooks" -maxdepth 1 -name "*.sh" -type f | wc -l)
AGENTS_COUNT=$(find "$CLAUDE_CONFIG_DIR/agents" -maxdepth 1 -name "*.md" -type f | wc -l)

echo "Claude Code sandbox bootstrap OK"
echo "  CLAUDE_CONFIG_DIR=$CLAUDE_CONFIG_DIR"
echo "  HOME=$HOME"
echo "  Skills: $SKILLS_COUNT"
echo "  Hooks:  $HOOKS_COUNT"
echo "  Agents: $AGENTS_COUNT"
