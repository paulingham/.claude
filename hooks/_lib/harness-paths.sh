#!/usr/bin/env bash
# Canonical root resolver for plugin + overlay portability.
# Source after log.sh. Safe under set -u (all expansions have defaults).
[[ -n "${_HARNESS_PATHS_LOADED:-}" ]] && return 0
_HARNESS_PATHS_LOADED=1
HARNESS_ROOT="${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}"
HARNESS_DATA="${CLAUDE_PLUGIN_DATA:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}"
export HARNESS_ROOT HARNESS_DATA
