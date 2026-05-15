#!/usr/bin/env bash
# Slice F — AC F7. Producer half of the [PlanValidationOutcome] marker
# contract whose consumer ships in slice-e (hooks/plan-cache-audit.sh).
#
# Usage: emit_outcome.sh <VERDICT>
#   VERDICT ∈ {PLAN_APPROVED, PLAN_HOLES, ROUTING_UPSHIFTED}
#
# Exit codes:
#   0 — verdict valid, marker emitted on stdout
#   2 — verdict invalid (no marker emitted)
#
# Marker shape (exact, slice-e regex anchored):
#   [PlanValidationOutcome] verdict: <VERDICT>
#
# Without this producer, slice-g's pv_pass_rate_on_hit stays 0 in production
# and the rollout-gate skill rejects every flip-to-on PR. Routed to slice-f
# from the slice-e code review under Iron Law 6 (in-cycle fix).

set -eu

verdict="${1:-}"
case "$verdict" in
  PLAN_APPROVED|PLAN_HOLES|ROUTING_UPSHIFTED)
    printf '[PlanValidationOutcome] verdict: %s\n' "$verdict"
    ;;
  *)
    printf 'emit_outcome.sh: invalid verdict %q (expected PLAN_APPROVED|PLAN_HOLES|ROUTING_UPSHIFTED)\n' \
      "$verdict" >&2
    exit 2
    ;;
esac
