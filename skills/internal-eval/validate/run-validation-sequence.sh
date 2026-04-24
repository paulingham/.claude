#!/usr/bin/env bash
# DELIVERY VALIDATION — proves the internal-eval flow end-to-end with a
# stubbed inner pipeline. Phase A baselines an all-pass run, Phase B injects
# ≥2 deterministic failures, Phase C asserts regression detection, Phase D
# restores the stub to all-pass, Phase E asserts a clean verdict. The live
# harness is NEVER mutated — byte-equivalence of agents/code-reviewer.md is
# verified across the sequence. Live-harness baseline capture is a separate
# ship-phase activity; this script proves the FLOW.

set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$HERE/lib/phase-runners.sh"
# shellcheck disable=SC1091
source "$HERE/lib/assertions.sh"
# shellcheck disable=SC1091
source "$HERE/lib/sequence-asserts.sh"

main() {
  local tmp="${1:-$(mktemp -d)}"
  local root; root="$(cd "$HERE/../../.." && pwd)"
  local sha_before; sha_before="$(shasum "$root/agents/code-reviewer.md" | awk '{print $1}')"
  _run_phases "$tmp"
  _run_assertions "$tmp" "$root" "$sha_before"
  echo "[validation] PASS — all 5 phases green (tmp=$tmp)"
}

_run_phases() {
  phase_a "$1"; _maybe_inject "$1"; phase_c "$1"; phase_d "$1"; phase_e "$1"
}

_maybe_inject() {
  local tmp="$1"
  [ "${VALIDATE_FORCE_CLEAN_INJECT:-0}" = "1" ] || { phase_b "$tmp"; return; }
  echo '{}' > "$tmp/manifest.json"
  run_suite_in "$tmp" "inject"
}

_run_assertions() {
  local tmp="$1"; local root="$2"; local sha_before="$3"
  run_phase_a_asserts "$tmp"
  run_phase_b_asserts "$tmp"
  run_phase_c_asserts "$tmp"
  run_phase_d_asserts "$root" "$sha_before"
  run_phase_e_asserts "$tmp"
}

main "$@"
