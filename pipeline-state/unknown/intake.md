---
task_id: unknown
classification: doc-only-harness-change
tier_emitted: T1
tier_initial: T1
detector_phase: rules
detector_confidence: high
user_phrasing_signals: []
phrasing_honoured: true
override_token: null
safety_override_fired: false
predicted_files:
  - hooks/_lib/quality-gate-checks.sh
  - tests/hooks/test_freshness_tier_carveout.bats
fingerprint_cost_tokens: 0
criticality_filtered_by_tier: false
---

# Intake — freshness gate T0/T1 carve-out (dogfooding stub)

This intake.md exists to exercise the new carve-out for this PR's own
`gh pr create` quality-gate. The change adds T0/T1 auto-pass behaviour
to `_qg_check_freshness`; without this stub the gate would block PR
creation on the same .md-only condition the PR is fixing.

The `unknown` task_id is the literal fallback `_qg_check_freshness` uses
when `CLAUDE_PIPELINE_TASK_ID` is unset (its `${CLAUDE_PIPELINE_TASK_ID:-unknown}`
default), so this stub fires for the ad-hoc `gh pr create` invocation
that has no active pipeline.
