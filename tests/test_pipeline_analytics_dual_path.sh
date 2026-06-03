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

# ---------------------------------------------------------------------------
# AC1 — script must source cleanly with CLAUDE_PLUGIN_ROOT and CLAUDE_CONFIG_DIR
# both unset. If log.sh is still sourced via the env-var path (line 11 before
# Fix A), the source will fail when neither env var is set and $HOME has been
# remapped to a temp dir that does not contain a .claude/hooks tree.
# ---------------------------------------------------------------------------
echo "Test test_analytics_survives_unset_plugin_env_vars"
TMP2=$(mktemp -d)
trap 'rm -rf "$TMP2"' EXIT

# Stage a minimal pipeline under HARNESS_DATA (HOME-based path).
mkdir -p "$TMP2/.claude/pipeline-state/task-env-test"
cat > "$TMP2/.claude/pipeline-state/task-env-test/pipeline.md" <<'EOF'
---
task_id: task-env-test
phase: reflect
verdict: in_progress
type: feature
complexity_budget: 3
---
EOF

OUT2=$(env -u CLAUDE_PLUGIN_ROOT -u CLAUDE_CONFIG_DIR HOME="$TMP2" bash "$HOOK" task-env-test 2>&1)
RC2=$?
# Must not crash with "No such file or directory" sourcing log.sh
if echo "$OUT2" | grep -qE "No such file or directory|_log_hook_start: command not found"; then
  echo "  FAIL: script crashed due to bad log.sh source path (rc=$RC2)"; echo "  output: $OUT2"
  FAIL=$((FAIL + 1))
elif [[ "$RC2" -ne 0 ]]; then
  echo "  FAIL: script exited non-zero without the expected crash pattern (rc=$RC2)"; echo "  output: $OUT2"
  FAIL=$((FAIL + 1))
else
  echo "  ok: script survived unset env vars (rc=$RC2)"; PASS=$((PASS + 1))
fi

# ---------------------------------------------------------------------------
# AC3 — when HARNESS_DATA points elsewhere, script must find state under the
# repo root (git rev-parse --show-toplevel)/pipeline-state/<task-id>/
# ---------------------------------------------------------------------------
echo "Test test_analytics_falls_back_to_repo_root_pipeline_dir"
TMP3=$(mktemp -d)
trap 'rm -rf "$TMP3"' EXIT

REPO_PIPELINE_DIR="$REPO_ROOT/pipeline-state"
TASK_FALLBACK="task-reporoot-fallback-$$"
mkdir -p "$REPO_PIPELINE_DIR/$TASK_FALLBACK"
# Ensure cleanup even if the test aborts
trap 'rm -rf "$TMP3" "$REPO_PIPELINE_DIR/$TASK_FALLBACK"' EXIT

cat > "$REPO_PIPELINE_DIR/$TASK_FALLBACK/pipeline.md" <<'EOF'
---
task_id: task-reporoot-fallback
phase: reflect
verdict: in_progress
type: feature
complexity_budget: 2
---
EOF

# HARNESS_DATA points to TMP3 — no pipeline state there, forcing the
# repo-root fallback path.
METRICS3="$TMP3/.claude/metrics/pipelines.jsonl"
mkdir -p "$TMP3/.claude"
OUT3=$(CLAUDE_PLUGIN_DATA="$TMP3/.claude" HOME="$TMP3" bash "$HOOK" "$TASK_FALLBACK" 2>&1)
RC3=$?
if [[ "$RC3" -eq 0 ]] && [[ -f "$METRICS3" ]]; then
  echo "  ok: script fell back to repo-root pipeline-state/ (rc=$RC3)"; PASS=$((PASS + 1))
else
  echo "  FAIL: script did not fall back to repo-root pipeline-state/ (rc=$RC3)"
  echo "  output: $OUT3"
  FAIL=$((FAIL + 1))
fi
rm -rf "$REPO_PIPELINE_DIR/$TASK_FALLBACK"

# ---------------------------------------------------------------------------
# Mutation guard: workstream-scoped repo-root fallback uses the workstream
# sub-path, not just the flat task-id path.
# Kills mutant: drop workstream branch in fallback (always uses flat path).
# ---------------------------------------------------------------------------
echo "Test test_analytics_falls_back_to_repo_root_workstream_pipeline_dir"
TMP4=$(mktemp -d)
trap 'rm -rf "$TMP4"' EXIT

WS_TASK_FALLBACK="ws-task-reporoot-$$"
WS_FALLBACK_DIR="$REPO_ROOT/pipeline-state/workstreams/test-ws/$WS_TASK_FALLBACK"
mkdir -p "$WS_FALLBACK_DIR"
trap 'rm -rf "$TMP4" "$WS_FALLBACK_DIR"' EXIT

cat > "$WS_FALLBACK_DIR/pipeline.md" <<'EOF'
---
task_id: ws-task-reporoot
phase: reflect
verdict: in_progress
type: feature
complexity_budget: 2
---
EOF
cat > "$WS_FALLBACK_DIR/build.md" <<'EOF'
---
task_id: ws-task-reporoot
phase: build
verdict: WS_BUILD_COMPLETE
---
EOF

METRICS4="$TMP4/.claude/metrics/pipelines.jsonl"
mkdir -p "$TMP4/.claude"
OUT4=$(CLAUDE_PLUGIN_DATA="$TMP4/.claude" HOME="$TMP4" bash "$HOOK" "workstreams/test-ws/$WS_TASK_FALLBACK" 2>&1)
RC4=$?
if [[ "$RC4" -eq 0 ]] && [[ -f "$METRICS4" ]] && grep -q '"build":"WS_BUILD_COMPLETE"' "$METRICS4"; then
  echo "  ok: workstream fallback used correct workstreams/ sub-path (rc=$RC4)"; PASS=$((PASS + 1))
else
  echo "  FAIL: workstream fallback did not resolve correctly (rc=$RC4)"
  echo "  output: $OUT4"
  [[ -f "$METRICS4" ]] && cat "$METRICS4" || echo "  (no metrics file)"
  FAIL=$((FAIL + 1))
fi
rm -rf "$WS_FALLBACK_DIR"

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1
