#!/usr/bin/env bash
# Pipeline Analytics — called by /pipeline Reflect step after pipeline completion
# Aggregates phase state files + trajectory into a single metrics record
# Usage: bash pipeline-analytics.sh <task-id>
#
# enforces: protocols/reflection-protocol.md:Pipeline Analytics
# protects: pipeline, forensics

source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "standalone"
trap 'log_hook_event $?' EXIT

set -uo pipefail

RAW_TASK_ID="${1:?Usage: pipeline-analytics.sh TASK_ID (or workstreams/WS/TASK_ID)}"

# Parse workstream-scoped task ids of the form `workstreams/{ws}/{task-id}`
# BEFORE sanitization. The intermediate slashes are part of the path
# structure, not the identifier — sanitizing them away collapses the path.
# Each path segment is sanitized independently to preserve traversal-resistance.
_sanitize_segment() { printf '%s' "${1//[^a-zA-Z0-9_.-]/}"; }
WORKSTREAM=""
if [[ "$RAW_TASK_ID" =~ ^workstreams/([^/]+)/([^/]+)$ ]]; then
  WORKSTREAM=$(_sanitize_segment "${BASH_REMATCH[1]}")
  TASK_ID=$(_sanitize_segment "${BASH_REMATCH[2]}")
else
  TASK_ID=$(_sanitize_segment "$RAW_TASK_ID")
fi

PIPELINE_DIR="$HOME/.claude/pipeline-state"
METRICS_DIR="$HOME/.claude/metrics"
mkdir -p "$METRICS_DIR"

# Resolve the per-task state directory honouring workstream scope.
if [[ -n "$WORKSTREAM" ]]; then
  TASK_STATE_DIR="$PIPELINE_DIR/workstreams/${WORKSTREAM}/${TASK_ID}"
else
  TASK_STATE_DIR="$PIPELINE_DIR/${TASK_ID}"
fi

# DUAL_PATH: prefer new layout, fall back to legacy (legacy form has no
# canonical workstream variant — workstream pipelines only exist under the
# new layout — so the legacy fallback is root-scoped only).
PIPELINE_FILE="$TASK_STATE_DIR/pipeline.md"
[[ -f "$PIPELINE_FILE" ]] || PIPELINE_FILE="$PIPELINE_DIR/${TASK_ID}-pipeline.md"
if [[ ! -f "$PIPELINE_FILE" ]]; then
  echo "ERROR: Pipeline file not found for task $RAW_TASK_ID" >&2
  exit 1
fi

# Extract a field value from YAML frontmatter in a markdown file
extract_field() {
  local file="$1" field="$2"
  sed -n '/^---$/,/^---$/p' "$file" \
    | grep "^${field}:" \
    | head -1 \
    | sed "s/^${field}: *//"
}

TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
PROJECT=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")

# Read phase verdicts from individual phase state files
# Use simple variables instead of associative arrays (macOS bash 3.2 compat)
VERDICT_BUILD=""
VERDICT_REVIEW=""
VERDICT_VERIFY=""
VERDICT_TEST=""
VERDICT_ACCEPT=""
VERDICT_SHIP=""

# DUAL_PATH: glob phase files from new-layout subdir AND legacy flat form.
# Legacy form is root-scoped only — workstream pipelines never existed in the
# legacy flat layout, so we glob only the root flat form for backwards compat.
for PHASE_FILE in "$TASK_STATE_DIR"/*.md "$PIPELINE_DIR/${TASK_ID}"-*.md; do
  [[ "$PHASE_FILE" == *"-pipeline.md" ]] && continue
  [[ "$PHASE_FILE" == */pipeline.md ]] && continue
  [[ ! -f "$PHASE_FILE" ]] && continue

  PHASE_NAME=$(extract_field "$PHASE_FILE" "phase")
  VERDICT=$(extract_field "$PHASE_FILE" "verdict")
  case "$PHASE_NAME" in
    build)  VERDICT_BUILD="$VERDICT" ;;
    review) VERDICT_REVIEW="$VERDICT" ;;
    verify) VERDICT_VERIFY="$VERDICT" ;;
    test)   VERDICT_TEST="$VERDICT" ;;
    accept) VERDICT_ACCEPT="$VERDICT" ;;
    ship)   VERDICT_SHIP="$VERDICT" ;;
  esac
done

# Count agents from trajectory file (DUAL_PATH).
TRAJECTORY_FILE="$TASK_STATE_DIR/trajectory.jsonl"
[[ -f "$TRAJECTORY_FILE" ]] || TRAJECTORY_FILE="$PIPELINE_DIR/${TASK_ID}-trajectory.jsonl"
AGENT_COUNT=0
if [[ -f "$TRAJECTORY_FILE" ]]; then
  AGENT_COUNT=$(wc -l < "$TRAJECTORY_FILE" | tr -d ' ')
fi

# Count review rounds from review phase files (DUAL_PATH, same layout rules).
REVIEW_ROUNDS=0
for PHASE_FILE in "$TASK_STATE_DIR"/review*.md "$PIPELINE_DIR/${TASK_ID}"-review*.md; do
  [[ -f "$PHASE_FILE" ]] && ((REVIEW_ROUNDS++)) || true
done
[[ "$REVIEW_ROUNDS" -eq 0 ]] && REVIEW_ROUNDS=1

# Extract complexity budget and type from pipeline file
COMPLEXITY=$(extract_field "$PIPELINE_FILE" "complexity_budget")
TYPE=$(extract_field "$PIPELINE_FILE" "type")

# Build the analytics record and append to pipelines.jsonl
jq -c -n \
  --arg ts "$TIMESTAMP" \
  --arg task_id "$TASK_ID" \
  --arg project "$PROJECT" \
  --arg type "${TYPE:-unknown}" \
  --argjson complexity "${COMPLEXITY:-0}" \
  --argjson agent_count "$AGENT_COUNT" \
  --argjson review_rounds "$REVIEW_ROUNDS" \
  --arg build_verdict "$VERDICT_BUILD" \
  --arg review_verdict "$VERDICT_REVIEW" \
  --arg verify_verdict "$VERDICT_VERIFY" \
  --arg test_verdict "$VERDICT_TEST" \
  --arg accept_verdict "$VERDICT_ACCEPT" \
  --arg ship_verdict "$VERDICT_SHIP" \
  '{
    timestamp: $ts,
    task_id: $task_id,
    project: $project,
    type: $type,
    complexity_budget: $complexity,
    agents_spawned: $agent_count,
    review_rounds: $review_rounds,
    phases: {
      build: $build_verdict,
      review: $review_verdict,
      verify: $verify_verdict,
      test: $test_verdict,
      accept: $accept_verdict,
      ship: $ship_verdict
    }
  }' >> "$METRICS_DIR/pipelines.jsonl" 2>/dev/null

echo "Analytics recorded for pipeline $TASK_ID"
exit 0
