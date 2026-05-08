# Wave 2a-B3 — Follow-ups

## v2: Severity-floor auto-promotion (Alt C)

Promote severity-floor (auto-promote `drop`→`unsure` on
`sast_severity == CRITICAL`) to v2 when EITHER:

(a) ≥1 `drop` verdict on `sast_severity=CRITICAL` finding appears in any
    project's `metrics/*/sast-triage.jsonl` across any pipeline (one CRITICAL
    false-drop is enough), OR

(b) ≥10 `drop` verdicts on `sast_severity=HIGH` findings across ≥3 distinct
    pipelines.

**Trigger evaluation runs in `/learn` Step 7c.** When trigger fires, `/learn`
emits actionable instinct (`sast-triage-severity-floor-needed`, confidence 0.7)
targeting architect and security-engineer roles, AND adds an item to
`pipeline-state/health-reports/{date}.md`.

## v2: Batched triage

When `metrics/$SESSION/sast-triage.jsonl` has accumulated 200+ records across
10+ pipelines, evaluate batched triage (10 findings per LLM call, single
JSON array out). Use the `rationale_excerpt` field to compare batched vs
per-finding rationale quality.

## Rung 4 alternative SAST tools

Currently rung 3 only invokes Semgrep. CodeQL and Bearer are accepted via
SARIF (rungs 1+2 staged path) but have no on-demand fallback. If staged-SARIF
adoption is low, add a vendor-agnostic on-demand rung.
