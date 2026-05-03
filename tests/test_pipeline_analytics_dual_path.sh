#!/usr/bin/env bash
# Slice B — pipeline-analytics.sh globs phase files under {task-id}/ subdir.
# AC #4. Stub: analytics_globs_phase_files_under_subdir.
set -uo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
HOOK="$REPO_ROOT/hooks/pipeline-analytics.sh"
[[ -x "$HOOK" ]] || { echo "FAIL: hook not executable: $HOOK"; exit 1; }

PASS=0; FAIL=0
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/.claude"; ln -s "$REPO_ROOT/hooks" "$TMP/.claude/hooks"

mkdir -p "$TMP/.claude/pipeline-state/t1"
cat > "$TMP/.claude/pipeline-state/t1/pipeline.md" <<'EOF'
---
task_id: t1
phase: reflect
verdict: in_progress
type: feature
complexity_budget: 5
---
EOF
cat > "$TMP/.claude/pipeline-state/t1/build.md" <<'EOF'
---
task_id: t1
phase: build
verdict: BUILD_COMPLETE
---
EOF

echo "Test analytics_globs_phase_files_under_subdir"
HOME="$TMP" bash "$HOOK" t1 >/dev/null 2>&1
RC=$?
METRICS_FILE="$TMP/.claude/metrics/pipelines.jsonl"
if [[ "$RC" -eq 0 && -f "$METRICS_FILE" ]] && grep -q '"build":"BUILD_COMPLETE"' "$METRICS_FILE"; then
  echo "  ok: analytics found new-layout phase files"; PASS=$((PASS + 1))
else
  echo "  FAIL: analytics did not pick up new-layout phase files (rc=$RC)"; FAIL=$((FAIL + 1))
  [[ -f "$METRICS_FILE" ]] && cat "$METRICS_FILE" || echo "  (no metrics file)"
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1
