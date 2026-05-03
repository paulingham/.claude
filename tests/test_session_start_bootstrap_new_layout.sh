#!/usr/bin/env bash
# Slice B — session-start-bootstrap lists new-layout active pipelines.
# AC #4. Stub: bootstrap_lists_new_layout_active_pipelines.
set -uo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
HOOK="$REPO_ROOT/hooks/session-start-bootstrap.sh"
[[ -x "$HOOK" ]] || { echo "FAIL: hook not executable: $HOOK"; exit 1; }

PASS=0; FAIL=0
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/.claude"; ln -s "$REPO_ROOT/hooks" "$TMP/.claude/hooks"
mkdir -p "$TMP/.claude/pipeline-state/t1"
cat > "$TMP/.claude/pipeline-state/t1/pipeline.md" <<'EOF'
---
task_id: t1
verdict: in_progress
---

## Phases
- Build: in_progress
EOF

echo "Test bootstrap_lists_new_layout_active_pipelines"
OUT=$(HOME="$TMP" bash "$HOOK" 2>/dev/null || true)
if echo "$OUT" | grep -q "ACTIVE PIPELINES" && echo "$OUT" | grep -q "t1"; then
  echo "  ok: bootstrap lists new-layout pipeline"; PASS=$((PASS + 1))
else
  echo "  FAIL: t1 not listed in bootstrap output"; FAIL=$((FAIL + 1))
  echo "$OUT" | head -20
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1
