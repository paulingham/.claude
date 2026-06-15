#!/usr/bin/env bash
# arch-fitness-gate.sh — SubagentStop ADVISORY (NOT ENFORCED) hook.
# Detects import cycles in hooks/_lib after every subagent completes.
# Writes findings to: $HARNESS_DATA/metrics/$SESSION_ID/arch-fitness.jsonl
#
# KNOWN FALSE-NEGATIVE: static import/from-import only; importlib.spec_from_file_location
# dynamic loads + hyphenated-stem cycles are NOT detected.
#
# PROMOTION CRITERION: flip to enforcing (exit 2 on cycle) after >=10 distinct
# sessions logged with ZERO cycle-findings; until then advisory log+stderr only.
#
# Iron Law 8 [ASPIRATIONAL] fail-closed applies to the UNEVALUABLE-INPUT path
# (python3-absent/detector-crash -> SKIPPED not clean), NOT the cycle-found
# path (advisory exit-0 by design).
#
# enforces: rules/core.md Iron Law 8 [ASPIRATIONAL] (unevaluable-input path only)
# protects: pipeline (advisory architecture-fitness telemetry only)
# Skips on stop_hook_active to prevent duplicate arch-fitness JSONL rows in nested calls.
set -uo pipefail

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_lib/harness-paths.sh"
# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_lib/log.sh"
_log_hook_start
_log_hook_trigger "SubagentStop"
trap 'log_hook_event $?' EXIT

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/hook-profile.sh" 2>/dev/null && check_hook_profile "standard" || exit 0

_arch_log() {
  local msg="$1" ts sid dir
  ts=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo "unknown")
  sid="${CLAUDE_SESSION_ID:-local-$$}"
  sid="${sid//[^A-Za-z0-9_-]/}"
  [[ -z "$sid" ]] && sid="unknown"
  dir="${HARNESS_DATA}/metrics/${sid}"
  mkdir -p "$dir" 2>/dev/null || return 0
  printf '{"timestamp":"%s","hook":"arch-fitness-gate","session_id":"%s","finding":"%s"}\n' \
    "$ts" "$sid" "$msg" >> "${dir}/arch-fitness.jsonl" 2>/dev/null || true
}

INPUT=$(cat 2>/dev/null) || exit 0
[[ -z "$INPUT" ]] && exit 0

STOP_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false' 2>/dev/null || echo "false")
[[ "$STOP_ACTIVE" == "true" ]] && { trap - EXIT; exit 0; }

command -v python3 >/dev/null 2>&1 || { _arch_log "SKIPPED: python3 absent"; exit 0; }

LIB="${HARNESS_ROOT}/hooks/_lib"
[[ -d "$LIB" ]] || { _arch_log "SKIPPED: _lib not found"; exit 0; }

OUT=$(python3 "${LIB}/arch_fitness_cli.py" "$LIB" 2>/dev/null)
rc=$?
(( rc != 0 )) && { _arch_log "SKIPPED: detector error rc=${rc}"; exit 0; }

if [[ "$OUT" == "[]" ]]; then
  _arch_log "clean: 0 cycles"
else
  _arch_log "ADVISORY cycles=${OUT}"
  echo "[arch-fitness] ADVISORY: import cycle in hooks/_lib: ${OUT}" >&2
fi

exit 0
