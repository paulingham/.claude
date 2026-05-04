---
task_id: wave4-verification-depth
phase: build
verdict: pending
timestamp: 2026-05-04T00:10:00Z
type: batch
designated_branch: claude/add-property-based-testing-uaI6y
pr: 69
---

## Batch: Wave 4 — Verification depth (A2/A3/A6/A7)

Closes the "agent-written tests pass falsely" failure class via four sub-bundles
sharing the verification-depth theme. Pre-planned ACs from user; no Plan phase.

## Tasks

| ID | Description | Phase | Verdict |
|----|-------------|-------|---------|
| A2.1 | qa-test-strategy: insert "Property-Based Coverage" step | build | pending |
| A2.2 | qa-engineer: add property-testing instinct_category + checklist item | build | pending |
| A2.3 | rules/_detail/engineering-invariants.md: add Tier 1.5 PBT to § Proof of Correctness | build | pending |
| A3.2 | settings.json: add typescript-language-server + pyright MCP entries; SE/FE tool allowlists; tests snapshot | build | pending |
| A3.3 | learning/instincts/lsp-feedback-first.md: confidence 0.6, roles SE+FE | build | pending |
| A6.1 | tool-synthesis: extend triggers + emit TOOL_SYNTHESISED_PROMOTABLE | build | pending |
| A6.2 | learn: scan observations for promotion markers; scaffold permanent skills | build | pending |
| A6.3 | tool-synthesis: "Why this works" note citing arXiv 2511.13646 | build | pending |
| A7.1 | intake: insert "Contract Identification" step producing `## Contracts Touched` | build | pending |
| A7.2 | build-implementation: insert "Write Contract Assertions" between Read AC Stubs and Batched RED | build | pending |
| A7.3 | rules/_detail/engineering-invariants.md: add Tier 0 (Contracts) to § Proof of Correctness | build | pending |
| meta | rules/verdict-catalog.md: add TOOL_SYNTHESISED_PROMOTABLE entry (harness-audit gate) | build | pending |
