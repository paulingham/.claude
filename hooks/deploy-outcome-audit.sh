#!/usr/bin/env bash
# Deploy outcome audit — PostToolUse hook (no matcher; internal Skill guard).
# Parses [Deploy] outcome: <X> pipeline_id: <Y> environment: <Z> from Skill
# tool_response and appends one deploy_outcome record to
# learning/<project-hash>/observations.jsonl.
# NEVER blocks (exit 0 on every path). Advisory telemetry only.
#
# WHY project-hash via origin URL: _project_hash hashes git remote origin —
# identical from both the main repo cwd AND any linked worktree sharing that
# origin. This guarantees deploy_outcome records land in the same
# observations.jsonl regardless of which worktree the Skill fires from.
# If escape_rate stays absent despite known deploys, grep
# learning/<hash>/observations.jsonl and compare the hash against
# skills/learn/SKILL.md Step 1 (hash-divergence diagnostic).
#
# enforces: protocols/pipeline-protocol.md
# protects: learning, escape_rate telemetry

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/harness-paths.sh"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/project-hash.sh"
# shellcheck source=/dev/null
source "${HOOK_DIR}/hook-profile.sh" 2>/dev/null && check_hook_profile "standard" || exit 0

INPUT=$(cat)
TOOL=$(printf '%s' "$INPUT" | jq -r '.tool_name // ""' 2>/dev/null)
[[ "$TOOL" != "Skill" ]] && exit 0

RESPONSE=$(printf '%s' "$INPUT" | jq -r '.tool_response // ""' 2>/dev/null)
MARKER=$(printf '%s' "$RESPONSE" | grep -oE '\[Deploy\] outcome: [A-Za-z0-9._-]+ pipeline_id: [A-Za-z0-9._-]+ environment: [A-Za-z0-9._-]+' | tail -1)
[[ -z "$MARKER" ]] && exit 0

OUTCOME=$(printf '%s' "$MARKER"   | sed 's/.*outcome: //'     | awk '{print $1}')
PIPELINE=$(printf '%s' "$MARKER"  | sed 's/.*pipeline_id: //' | awk '{print $1}')
ENVIRON=$(printf '%s' "$MARKER"   | sed 's/.*environment: //' | awk '{print $1}')

if [[ ! "$OUTCOME"  =~ ^[A-Za-z0-9._-]+$ ]] || \
   [[ ! "$PIPELINE" =~ ^[A-Za-z0-9._-]+$ ]] || \
   [[ ! "$ENVIRON"  =~ ^[A-Za-z0-9._-]+$ ]]; then
  exit 0
fi

TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
PROJECT_HASH=$(_project_hash --fallback "$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")")
BASE_DIR="${HARNESS_DATA}/learning/${PROJECT_HASH}"

python3 "${HOOK_DIR}/_lib/deploy-outcome-emit.py" \
  "$BASE_DIR" "$TS" "$PIPELINE" "$OUTCOME" "$ENVIRON" 2>/dev/null || true

exit 0
