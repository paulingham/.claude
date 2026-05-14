---
id: instinct-architect-recon-high-leverage
confidence: 0.60
category: pattern
domain: workflow
scope: project
project: 8efffd88329f34786e1828737702e911
roles: [pipeline-orchestrator]
applies_to_roles: [pipeline-orchestrator]
source: pipeline-analytics
created: 2026-05-14T00:00:00Z
evidence_count: 1
last_seen: 2026-05-14T00:00:00Z
---

## Pattern
The `architect-context-recon` 3-mode parallel dispatch (code-archaeology / memory-mining / domain-analysis) is high-leverage on critical or budget>=7 pipelines that reference an existing proposal or spec — it routinely surfaces 25-40 findings + 5-10 spec corrections BEFORE the architect drafts the plan, preventing rework rounds downstream.

**Why**: on the iron-law-2-freshness-hook pipeline, recon surfaced 30 findings + 10 anti-findings + 5 concrete spec corrections to the source proposal (wrong helper filename, wrong hook index, wrong promotion-decision claim, wrong line-replace vs append for prose, wrong version stamp). These were reconciled in the architect's round-1 plan — without recon, they would have surfaced as plan-validation HIGH findings instead, forcing a round-2 architect re-spawn.

**How to apply**: when intake flags `critical=true` OR `budget>=7` AND the task references an external proposal/spec file (PR body, design doc, RFC), dispatch the 3 architect-context-recon modes in parallel BEFORE the architect Plan dispatch. Default to all 3 modes (code-archaeology, memory-mining, domain-analysis) — they parallelise cleanly and produce orthogonal output to a single concatenated `architect-context.md` file.

Skip recon only when (a) task is non-critical AND budget<7, OR (b) the task is a 1-2 file mechanical change (e.g., dependency bump, simple rename) where the architect can read the change site directly without precedent context.

## Evidence
- 2026-05-14: iron-law-2-freshness-hook — recon surfaced 5 spec corrections that the architect baked into the round-1 plan, leading to plan-validation round-1 CHANGES_REQUESTED on different (deeper) holes rather than the surface-level spec errors. Round 2 cleanly addressed those holes.
