#!/usr/bin/env bash
# Gap 3 — pipeline-analytics.sh must handle workstream-scoped task ids.
# Before this fix the script sanitized the task-id by stripping `/`, so
# `workstreams/ws/task` collapsed to `workstreamswstask` and failed to locate
# the pipeline file. Workstream-scoped pipelines never got analytics.
set -uo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
HOOK="$REPO_ROOT/hooks/pipeline-analytics.sh"
[[ -x "$HOOK" ]] || { echo "FAIL: hook not executable: $HOOK"; exit 1; }

PASS=0; FAIL=0
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/.claude"; ln -s "$REPO_ROOT/hooks" "$TMP/.claude/hooks"

# Stage a workstream-scoped pipeline at the canonical new-layout path:
# pipeline-state/workstreams/{ws}/{task-id}/{phase}.md
mkdir -p "$TMP/.claude/pipeline-state/workstreams/foo/bar"
cat > "$TMP/.claude/pipeline-state/workstreams/foo/bar/pipeline.md" <<'EOF'
---
task_id: bar
phase: reflect
verdict: in_progress
type: feature
complexity_budget: 5
---
EOF
cat > "$TMP/.claude/pipeline-state/workstreams/foo/bar/build.md" <<'EOF'
---
task_id: bar
phase: build
verdict: BUILD_COMPLETE
---
EOF

echo "Test analytics_resolves_workstream_scoped_task_id"
HOME="$TMP" bash "$HOOK" workstreams/foo/bar >/dev/null 2>&1
RC=$?
METRICS_FILE="$TMP/.claude/metrics/pipelines.jsonl"
if [[ "$RC" -eq 0 && -f "$METRICS_FILE" ]] && grep -q '"build":"BUILD_COMPLETE"' "$METRICS_FILE"; then
  echo "  ok: analytics resolved workstream-scoped task id"; PASS=$((PASS + 1))
else
  echo "  FAIL: analytics did not resolve workstream-scoped task id (rc=$RC)"
  FAIL=$((FAIL + 1))
  [[ -f "$METRICS_FILE" ]] && cat "$METRICS_FILE" || echo "  (no metrics file)"
fi

echo "Test analytics_still_works_for_root_task_id"
# Regression guard: root-layout pipelines still work after the workstream fix.
mkdir -p "$TMP/.claude/pipeline-state/baz"
cat > "$TMP/.claude/pipeline-state/baz/pipeline.md" <<'EOF'
---
task_id: baz
phase: reflect
verdict: in_progress
type: feature
complexity_budget: 5
---
EOF
cat > "$TMP/.claude/pipeline-state/baz/build.md" <<'EOF'
---
task_id: baz
phase: build
verdict: BUILD_COMPLETE
---
EOF
rm -f "$METRICS_FILE"
HOME="$TMP" bash "$HOOK" baz >/dev/null 2>&1
RC=$?
if [[ "$RC" -eq 0 && -f "$METRICS_FILE" ]] && grep -q '"task_id":"baz"' "$METRICS_FILE"; then
  echo "  ok: root-layout still resolves"; PASS=$((PASS + 1))
else
  echo "  FAIL: root-layout regression (rc=$RC)"; FAIL=$((FAIL + 1))
  [[ -f "$METRICS_FILE" ]] && cat "$METRICS_FILE" || echo "  (no metrics file)"
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1
