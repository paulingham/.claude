#!/usr/bin/env bash
# seed-user-settings — SessionStart hook.
#
# Seeds 9 developer-facing toggles + _doc_ siblings into the user-level
# settings.json so toggles moved to the user layer by PR #245 are editable.
# Delegates all logic to seed_user_settings.py (merge-only, fail-closed).
#
# python3 absent → exit 0 (fail-OPEN: missing seed is behaviour-preserving).
# Always exits 0 — never blocks SessionStart.

command -v python3 >/dev/null 2>&1 || exit 0
exec python3 "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/seed_user_settings.py"
