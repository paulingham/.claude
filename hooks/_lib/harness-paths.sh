#!/usr/bin/env bash
# Canonical root resolver for plugin + overlay portability.
# Source after log.sh. Safe under set -u (all expansions have defaults).
#
# CLAUDE_PLUGIN_ROOT and CLAUDE_PLUGIN_DATA MUST be absolute paths with no
# trailing slash. An empty string is treated as unset (falls back to the next
# tier in the precedence chain).
# Precedence:
#   HARNESS_ROOT: CLAUDE_PLUGIN_ROOT > CLAUDE_CONFIG_DIR > $HOME/.claude  (code/repo paths)
#   HARNESS_DATA: CLAUDE_PLUGIN_DATA > CLAUDE_CONFIG_DIR > $HOME/.claude  (runtime state paths)
[[ -n "${_HARNESS_PATHS_LOADED:-}" ]] && return 0
_HARNESS_PATHS_LOADED=1
HARNESS_ROOT="${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}"
HARNESS_DATA="${CLAUDE_PLUGIN_DATA:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}"
[[ "$HARNESS_DATA" = /* ]] || { echo "harness-paths: HARNESS_DATA must be absolute" >&2; return 1; }
[[ "$HARNESS_ROOT" = /* ]] || { echo "harness-paths: HARNESS_ROOT must be absolute" >&2; return 1; }
export HARNESS_ROOT HARNESS_DATA
