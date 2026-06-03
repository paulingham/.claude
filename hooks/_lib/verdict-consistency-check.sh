#!/usr/bin/env bash
# Verdict-consistency callable. Extracts the bidirectional consistency check
# from `skills/harness-audit/SKILL.md` § verdict-consistency (Section 2d) so
# bats, /harness-audit, and any other caller can invoke the same logic.
#
# Contract (see protocols/verdict-catalog.md and the plan-state plan.md § C5):
# - Exits 0 when every catalog row's verdict is emitted by at least one skill
#   AND every skill-frontmatter verdict is declared in the catalog.
# - Exits 1 with a single-line diagnostic on stdout:
#     missing-in-catalog: <VERDICT>
#     missing-in-skill: <VERDICT>
#
# Configuration directory resolution mirrors `_haf_check_settings_json` in
# `hooks/_lib/harness-audit-fast.sh` — honour CLAUDE_CONFIG_DIR for tests,
# default to $HOME/.claude in production. Delegates the parsing work to the
# Python helper to keep the bash entry under the protocols/operational-protocol
# shape budget AND to reuse the regex from `tests/test_verdict_catalog_audit.py`.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/harness-paths.sh"
HELPER="$SCRIPT_DIR/verdict_consistency.py"

if [ ! -d "$HARNESS_ROOT" ]; then
  echo "error: config-dir-not-found"
  exit 1
fi

if [ ! -f "$HELPER" ]; then
  echo "error: helper-not-found"
  exit 1
fi

exec python3 "$HELPER" "$HARNESS_ROOT"
