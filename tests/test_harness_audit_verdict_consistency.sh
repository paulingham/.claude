#!/usr/bin/env bash
# AC4 — /harness-audit verdict-consistency step passes after slice-a edits.
#
# Invokes hooks/_lib/verdict-consistency-check.sh with CLAUDE_CONFIG_DIR pointing
# at this worktree (the harness-repo root) and asserts exit 0.
#
# CROSS-SLICE NOTE: This test only validates the REVERSE direction (every catalog
# row's emitter resolves to a real skill/agent). The Python helper at
# hooks/_lib/verdict_consistency.py treats "emitter resolves" as "directory
# exists" (see _emitter_resolves in tests/test_verdict_catalog_audit.py:126-133),
# so the three new DOM_SMOKE_* rows pass reverse-consistency as soon as the
# `skills/build-implementation/` directory exists (it already does, regardless
# of slice-b's authoring). The FORWARD direction (skill's frontmatter `verdict:`
# declares DOM_SMOKE_*) is asserted by slice-b's own tests against
# skills/build-implementation/SKILL.md and is intentionally NOT enforced here.
set -uo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
CHECK="$REPO_ROOT/hooks/_lib/verdict-consistency-check.sh"

PASS=0; FAIL=0

echo "Test audit_verdict_consistency_passes"

[[ -x "$CHECK" ]] || { echo "  FAIL: check script not executable: $CHECK"; exit 1; }

OUT=$(CLAUDE_CONFIG_DIR="$REPO_ROOT" "$CHECK" 2>&1)
RC=$?

if [[ "$RC" -eq 0 ]]; then
  echo "  ok: verdict-consistency-check.sh exit 0"; PASS=$((PASS + 1))
else
  echo "  FAIL: verdict-consistency-check.sh exit $RC: $OUT"; FAIL=$((FAIL + 1))
fi

# Sanity probe — confirm the new rows are present (forward smoke against the
# catalog; reverse is what the script just checked).
CATALOG="$REPO_ROOT/rules/verdict-catalog.md"
for verdict in DOM_SMOKE_PASSED DOM_SMOKE_SKIPPED DOM_SMOKE_FAILED; do
  if grep -qE "^\\| \`${verdict}\`" "$CATALOG"; then
    echo "  ok: catalog row present: $verdict"; PASS=$((PASS + 1))
  else
    echo "  FAIL: catalog row missing: $verdict"; FAIL=$((FAIL + 1))
  fi
done

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1
