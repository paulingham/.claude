#!/usr/bin/env bash
# Pipeline Analytics — called by /pipeline Reflect step after pipeline completion
# Aggregates phase state files + trajectory into a single metrics record
# Usage: bash pipeline-analytics.sh <task-id>

source ~/.claude/hooks/_lib/log.sh
_log_hook_start
_log_hook_trigger "standalone"
trap 'log_hook_event $?' EXIT

set -uo pipefail

TASK_ID="${1:?Usage: pipeline-analytics.sh <task-id>}"

# Sanitize task ID to prevent path traversal
TASK_ID="${TASK_ID//[^a-zA-Z0-9_.-]/}"

PIPELINE_DIR="$HOME/.claude/pipeline-state"
METRICS_DIR="$HOME/.claude/metrics"
mkdir -p "$METRICS_DIR"

PIPELINE_FILE="$PIPELINE_DIR/${TASK_ID}-pipeline.md"
if [[ ! -f "$PIPELINE_FILE" ]]; then
  echo "ERROR: Pipeline file not found: $PIPELINE_FILE" >&2
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

for PHASE_FILE in "$PIPELINE_DIR/${TASK_ID}"-*.md; do
  [[ "$PHASE_FILE" == *"-pipeline.md" ]] && continue
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

# Count agents from trajectory file
TRAJECTORY_FILE="$PIPELINE_DIR/${TASK_ID}-trajectory.jsonl"
AGENT_COUNT=0
if [[ -f "$TRAJECTORY_FILE" ]]; then
  AGENT_COUNT=$(wc -l < "$TRAJECTORY_FILE" | tr -d ' ')
fi

# Count review rounds from review phase files
REVIEW_ROUNDS=0
for PHASE_FILE in "$PIPELINE_DIR/${TASK_ID}"-review*.md; do
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
