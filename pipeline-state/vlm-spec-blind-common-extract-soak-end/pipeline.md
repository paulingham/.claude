---
task_id: vlm-spec-blind-common-extract-soak-end
phase: placeholder
verdict: SOAK_PENDING
not_before: 2026-06-09T00:00:00Z
created_by: design-qc-visual-regression (slice-a-pixel-diff-pump)
created_at: 2026-05-12T23:45:00Z
---

# Soak-End Placeholder: Extract `_lib/tool-isolation-guard-common.sh`

This placeholder anchors a follow-up consolidation pipeline that may run once
the spec-blind V2 soak ends on **2026-06-09**. SessionStart's active-pipeline
scan reads the `not_before:` anchor and surfaces this file only after that date.

## Consolidation Targets

Two parallel-cloned guard libraries exist today, with renamed prefixes
(`_spec_blind_*` and `_vlm_critic_*`) but otherwise byte-near-identical bodies:

- `hooks/_lib/spec-blind-guard-common.sh` — three public functions
  (`_spec_blind_parse_input`, `_spec_blind_redact`, `_spec_blind_log_violation`)
  plus session-id sanitization plus SEC-MED-1 six-pattern secret redaction.
- `hooks/_lib/vlm-critic-guard-common.sh` — three public functions
  (`_vlm_critic_parse_input`, `_vlm_critic_redact`, `_vlm_critic_log_violation`)
  plus identical session-id sanitization plus identical SEC-MED-1 redaction.

## Intended Consolidation

Extract a generic `hooks/_lib/tool-isolation-guard-common.sh` that exposes
three role-parameterised helpers (`_isolation_parse_input`,
`_isolation_redact`, `_isolation_log_violation` with `<role-name>` as a
required first arg). Re-implement the two clone files as thin shims that
source the generic library, preserving the existing public symbol names for
backward compatibility.

The clone-now / consolidate-later approach was forced by the spec-blind V2
soak constraint — modifying `_lib/spec-blind-*` before the soak ends would
break the soak-frozen contract.

## Why slice-a commits this (not slice-b)

The architect's plan § 10 row 9 originally said slice-b would commit this
placeholder. However, slice-a's Tier 0 contract test
(`tests/contract.spec.visual_regression_schema.py::test_soak_end_placeholder_file_exists_with_correct_not_before_anchor`)
asserts its presence. To keep slice-a's batched-RED → GREEN cycle clean,
slice-a creates the placeholder itself. Slice-b may extend this file with
its own clone-fact section if needed.
