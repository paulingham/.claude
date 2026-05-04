---
task_id: wave4-verification-depth
phase: intake
classification: feature
task_class: feature
critical: false
bestofn: false
multi_repo: false
budget: 14
scope: 3
ambiguity: 2
context_pressure: 3
novelty: 3
coordination: 3
timestamp: 2026-05-04T00:00:00Z
designated_branch: claude/add-property-based-testing-uaI6y
contracts_touched:
  - rules/_detail/atdd-procedure.md (Tier 1.5 PBT, Tier 0 Contracts — § Proof of Correctness lives in engineering-invariants.md, not atdd; honour-where-it-lives)
  - rules/_detail/engineering-invariants.md § Proof of Correctness (Tier 0 Contracts, Tier 1.5 PBT inserted into the canonical tier ladder)
  - skills/qa-test-strategy/SKILL.md (new Step "Property-Based Coverage")
  - skills/intake/SKILL.md (new Step "Contract Identification")
  - skills/build-implementation/SKILL.md (ATDD insertion: "Write Contract Assertions" between Read AC Stubs and Batched RED)
  - skills/tool-synthesis/SKILL.md (extended triggers + TOOL_SYNTHESISED_PROMOTABLE verdict + Why-this-works note)
  - skills/learn/SKILL.md (scan observations for promotion markers, scaffold permanent skills under skills/<tool-name>/)
  - agents/qa-engineer.md (instinct_categories += property-testing; new checklist item)
  - agents/software-engineer.md (tool allowlist += mcp_lsp_diagnostics_ts, mcp_lsp_diagnostics_py)
  - agents/frontend-engineer.md (tool allowlist += mcp_lsp_diagnostics_ts, mcp_lsp_diagnostics_py)
  - settings.json (mcpServers entries for typescript-language-server, pyright)
  - tests/test_agent_tools_spec.py (snapshot update for SE/FE allowlists)
  - learning/instincts/lsp-feedback-first.md (NEW; confidence 0.6, roles: software-engineer, frontend-engineer)
  - rules/verdict-catalog.md (NEW verdict TOOL_SYNTHESISED_PROMOTABLE — must be added to keep harness-audit verdict-consistency green)
---

## Summary

Wave 4 — Verification depth. Four sub-bundles aimed at closing the
"agent-written tests pass falsely" failure class:

- **A2**: Property-based testing as a new tier (§ Proof of Correctness Tier 1.5).
  Per-public-function PBT generation in qa-test-strategy with frozen
  counterexamples promoted to unit tests.
- **A3**: LSP-as-MCP wiring (typescript-language-server + pyright) into
  software-engineer/frontend-engineer toolchains; new
  `lsp-feedback-first` instinct; tests/test_agent_tools_spec.py snapshot
  update.
- **A6**: Live-SWE-agent self-rewriting tools — extend tool-synthesis triggers,
  emit TOOL_SYNTHESISED_PROMOTABLE, /learn scaffolds permanent skill on ≥3
  recurrences, "Why this works" cite to arXiv 2511.13646.
- **A7**: Spec-as-Contract (GS-TDD lift) — intake produces a
  `## Contracts Touched` section; build-implementation ATDD inserts a
  contract-assertions RED step between Read AC Stubs and Batched RED;
  Tier 0 Contracts joins the Proof of Correctness tier ladder.

## Routing Decision

**Budget = 14 (5+5 dimensions, 3+2+3+3+3) → "Must decompose before starting"**
per `rules/_detail/operational-protocol.md` thresholds (13-15 → use
`/epic-breakdown`).

This is harness code touching `rules/`, `hooks/`-adjacent (settings.json
mcpServers), `skills/`, `agents/`, and `learning/instincts/`. The
**Internal Eval Gate** (`rules/_detail/agent-protocol.md` § Internal Eval
Gate) applies: PR must run `/internal-eval run` and produce zero regressions
before merge.

## Scope Conflict (FLAGGED)

Designated branch `claude/add-property-based-testing-uaI6y` reads as
**A2-only** (property-based testing). The task bundle is A2 + A3 + A6 + A7.
Three options:

1. **Single PR, retitle branch** — keep A2/A3/A6/A7 on this branch but
   retitle the PR to "Wave 4 — Verification depth" so reviewers see the
   actual scope. This matches the wave3 batch pattern.
2. **A2 only on this branch, separate branches per sub-bundle** — A3, A6, A7
   each get their own `claude/...-{slug}-{nonce}` branch and PR. Safer for
   review granularity; more PRs.
3. **Decompose into per-AC stories with `/epic-breakdown`** — strict protocol
   compliance for budget 14, but produces 4-8 stories and N pipelines. Highest
   ceremony cost.

## Recommendation

Option 1 (single PR, retitle). Rationale: the four sub-bundles share the
"Verification depth" theme, the ACs are pre-specified (no design ambiguity
that would benefit from per-story Plan Validation), and the changes are
mostly orthogonal across files (low merge-conflict risk). This matches the
batch-pipeline pattern used for wave3.

If user disagrees, fall back to Option 2 (one branch per sub-bundle).

## Criticality

`critical: false` — none of the canonical critical keywords (payment, auth,
RBAC, prod incident) match the task scope. The work is high-impact harness
infrastructure but the criticality tag in `intake/SKILL.md § Step 2d` is
narrowly defined and does not fire here.

## Best-of-N

`bestofn: false` — `critical=false AND no [best-of-n] token in user request`.

## Multi-repo

`multi_repo: false` — single repo (`paulingham/.claude`).

## Pre-flight Findings

- Branch already on `claude/add-property-based-testing-uaI6y` (per task brief). No switch needed.
- Working tree status: clean at intake time (verified pre-flight).
- No active pipeline (`_psp_find_active_pipelines` returned empty).
- All target files exist on disk.
- `rules/_detail/engineering-invariants.md` § Proof of Correctness is the
  canonical home for tier additions (the user prompt mentioned
  atdd-procedure as a fallback "if C12 has shipped"; both files exist and
  the section lives in engineering-invariants — honour where it lives).

## Phase Output

```
[Intake] Classification: feature (harness — verification depth)
[Intake] CB Score: Scope=3, Ambiguity=2, Context=3, Novelty=3, Coordination=3 → Total=14
[Intake] Criticality: standard
[Intake] Best-of-N: disabled
[Intake] Multi-repo: no
[Intake] Routing: must decompose (Budget 14) — recommend Option 1 (single PR, retitle)
[Intake] Internal Eval Gate: REQUIRED (touches rules/, skills/, agents/)
[Intake] Verdict: ROUTED
```

## Next

User decision required on dispatch shape (Option 1 / 2 / 3) before invoking
`/pipeline` or `/batch-pipeline`. Surfaced because Budget=14 + branch-name
scope conflict together warrant explicit confirmation rather than autonomous
choice.
