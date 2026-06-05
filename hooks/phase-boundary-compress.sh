#!/usr/bin/env bash
# Phase-Boundary Context-Compression Step (advisory, CAT arXiv:2512.22087).
#
# Orchestrator-invoked at each phase transition in skills/pipeline/SKILL.md Step 3.
# Advisory mode: measures tokens_before/tokens_after, emits one JSONL record.
# Does NOT rewrite the handoff file (advisory-first, flip is a separate gated change).
# Escape hatch: CLAUDE_DISABLE_PHASE_BOUNDARY_COMPRESS=1 → exit 0, no-op.
#
# Usage: phase-boundary-compress.sh <phase_from> <phase_to> [handoff_file]
#
# enforces: protocols/pipeline-protocol.md (§ Next Phase Input enforcement stanza)
# metrics:  metrics/{session}/phase-boundary.jsonl

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=_lib/harness-paths.sh
source "${HOOK_DIR}/_lib/harness-paths.sh"
# shellcheck source=_lib/state-dir.sh
source "${HOOK_DIR}/_lib/state-dir.sh"

[[ "${CLAUDE_DISABLE_PHASE_BOUNDARY_COMPRESS:-0}" == "1" ]] && exit 0

PHASE_FROM="${1:-unknown}"
PHASE_TO="${2:-unknown}"
HANDOFF_FILE="${3:-}"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo "1970-01-01T00:00:00Z")"
SESSION_ID="${CLAUDE_SESSION_ID:-default}"
METRICS_DIR="${HARNESS_DATA}/metrics/${SESSION_ID}"

# Read handoff document: prefer explicit file arg, else empty string
DOC=""
if [[ -n "$HANDOFF_FILE" && -f "$HANDOFF_FILE" ]]; then
    DOC="$(cat "$HANDOFF_FILE")"
fi

# Invoke Python helper (advisory — never fails the pipeline)
python3 "${HOOK_DIR}/_lib/phase_boundary_tokens.py" \
    "$METRICS_DIR" "$TS" "$PHASE_FROM" "$PHASE_TO" "$DOC" 2>/dev/null || true

echo "phase-boundary: advisory measurement recorded (${PHASE_FROM} → ${PHASE_TO})" >&2

exit 0
