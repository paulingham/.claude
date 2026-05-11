---
task_id: spec-blind-validator-harness-aware-soak-end
phase: planned
verdict: PIPELINE_PLANNED
not_before: 2026-06-09
schema_version: 1
---

# Spec-Blind Validator V2 — Harness-Aware Allowlist (placeholder)

This is a placeholder pipeline scheduled for execution **30 days after the merge of the V1 spec-blind-validator pipeline**. SessionStart's active-pipeline scan surfaces it once the `not_before` date passes (anchor: 2026-05-10 V1 merge + 30 days = 2026-06-09).

## Why this pipeline exists

V1 emits `SPEC_BLIND_INSUFFICIENT_SURFACE` for harness-internal pipelines because the harness has no `interface.{ext}` or `index.*` of its own — it ships hooks, skills, agents, and protocol `.md` files. V2 augments the read-guard's allowlist to make spec-blind validation viable on the harness itself, preserving the spec-blind property by treating contract `.md` files as the harness's public surface.

## Scope (named here for forensic anchoring)

V2 augments `hooks/_lib/spec-blind-allow-paths.txt` with these new patterns:

- `rules/_detail/**.md` — harness contract surface (iron laws, protocol detail)
- `agents/*.md` — agent frontmatter + role definitions (orchestrator dispatch contract)
- `skills/**/SKILL.md` — skill frontmatter contracts (verdicts + dispatch shape)
- `orchestrator/**.md` — orchestrator-side procedure detail
- `CLAUDE.md` — top-level harness contract
- `hooks/_lib/**.txt` — sibling-file allowlists (e.g. `destructive-verbs.txt`, `spec-blind-test-runners.txt`)

**Out of scope**: `hooks/*.sh`, `hooks/_lib/*.sh` — those are implementation, not contract; they remain deny.

## Soak-end gate conditions

Before V2 ships:

1. ≥ 30 days elapsed since V1 merge (the `not_before` anchor).
2. Zero `SPEC_BLIND_BLOCKED` verdicts attributed to harness-internal cwd in the last 30 days of observations.
3. Three or more harness-internal pipelines logged `SPEC_BLIND_INSUFFICIENT_SURFACE` reason `harness-internal-recursion` — confirming the V2 surface is needed (not theoretical).

## Status

`PIPELINE_PLANNED` — no work begins until the `not_before` anchor passes AND the gate conditions clear. Operators may bring this pipeline forward by invoking it explicitly; otherwise SessionStart surfaces it on schedule.
