# Agent x Skill Matrix

_Reference: which agents own which skills, and which skills each agent reads occasionally. Generated 2026-05-04; regenerate when agent or skill definitions change. Validated against `orchestrator/agent-orchestration.md` and `orchestrator/parallel-dispatch-details.md`._

## Layout note

A strict 13-row x 59-column table is unreadable on any monitor and impossible to maintain. This file uses a hybrid layout: per-agent sections (primary view) listing each agent's primary and secondary skills, plus a skill-keyed reverse index (lookup view) showing which agent each skill spawns.

Cell semantics:

- **primary** — the agent canonically executes the skill's procedure. Validated by EITHER (a) a `subagent_type: "<role>"` line in the skill's spawn snippet OR the orchestrator's dispatch file, OR (b) the skill's frontmatter `agent: <role>` field.
- **secondary** — the agent reads the skill for context. Evidence: (a) the agent's own `.md` references the skill, (b) an orchestrator spawn prompt pairs the agent with the skill as supplementary reading, OR (c) the skill is canonically referenced from a workflow the agent runs.
- **blank** — no relationship.

## Inventory

- **Agents (13)**: architect, code-reviewer, database-engineer, fix-engineer, frontend-engineer, infrastructure-engineer, patch-critic, planning-agent, product-reviewer, qa-engineer, security-engineer, session-memory-updater, software-engineer.
- **Skills (59 with SKILL.md)** — alphabetised:
  - api-scaffold, batch-pipeline, bff-scaffold, bug-fix, build-implementation, capture, code-review, continuous-planning, creative-direction, cross-service-pipeline, db-migration, debug, debug-trace, deploy, deployment-verification, design-qc, design-system-init, embedder, epic-breakdown, estimation, eval-model-effectiveness, forensics, greenfield-scaffold, harness-audit, harness-config, health-scan, infra-scaffold, intake, internal-eval, learn, load-test, mcp_memory, microservices-scaffold, module-extraction, observability-setup, patch-critique, pipeline, pipeline-resume, plan-self-validation, polish, pr-creation, product-acceptance, project-setup, qa-test-strategy, react-native-patterns, recall, refactor, reindex-memory, security-review, service-extraction, skill-builder, story-writing, tech-spike, tool-synthesis, verify, voice-scaffold, web-frontend-patterns, workstream.
  - **Note**: `skills/_deferred/` is currently empty. A sibling slice (C2) is moving 5 skills into `_deferred/` — the move is organisational only. If a skill listed here later appears under `_deferred/`, the matrix entry stays valid (still invokable).
  - `skills/best-of-n/` exists but has NO SKILL.md (config + helpers only). Not a skill — a dispatch helper consumed by orchestrator code. Excluded from the count.
  - `skills/_template/` is the scaffold template, not a real skill. Excluded.

## Matrix — Per-Agent View

### architect

- **Primary** (skills the orchestrator spawns architect to execute):
  - `epic-breakdown` (`agent: architect`)
  - `estimation` (`agent: architect`)
  - `story-writing` (`agent: architect`)
  - `tech-spike` (`agent: architect`)
  - `plan-self-validation` (description: "Architect re-reads its own plan...")
- **Secondary** (read for context):
  - `continuous-planning` (planning-agent reads it; architect's plan is the input the planning-agent refines — architect re-reads on revision cycles)
  - `intake` (architect reads `pipeline-state/{task-id}/intake.md` § Contracts Touched at Plan phase per intake skill body)
  - `greenfield-scaffold` (orchestrator spawns architect twice during greenfield — discovery and UI architecture)

### code-reviewer

- **Primary**:
  - `code-review` (`agent: code-reviewer`; `subagent_type: "code-reviewer"` in skill body and orchestrator dispatch)
- **Secondary**:
  - `react-native-patterns` (orchestrator spawn prompt pairs it: "Also read ~/.claude/skills/react-native-patterns/SKILL.md for tech-specific guidance")
  - `web-frontend-patterns` (parallel reference for web stacks — same dispatch pattern)
  - `security-review` (run in parallel by sibling reviewer; review findings are consolidated)

### database-engineer

- **Primary**:
  - `db-migration` (`agent: database-engineer`)
- **Secondary**:
  - `build-implementation` (database-engineer is a build-phase role — applies the same ATDD cycle when migrations and schema changes are part of a slice)
  - `refactor` (schema refactors — same TDD discipline)

### fix-engineer

- **Primary**: _(no skill)_ — fix-engineer is dispatched WITHOUT a skill file. Its instructions are baked into the spawn prompt (cited finding + diff + verdict context per `agents/fix-engineer.md`). It does not execute a skill's procedure.
- **Secondary**:
  - `code-review` (reads the cited finding from a code-reviewer output)
  - `security-review` (same — cited finding from security-engineer)
  - `qa-test-strategy` (same — GAPS_FOUND finding)
  - `verify` (same — UNVERIFIED finding)
  - `patch-critique` (same — PATCH_REJECTED finding)
  - `product-acceptance` (same — REJECTED finding)
  - `bug-fix` (per-behaviour TDD applies if the finding requires a new test, per `agents/fix-engineer.md` § Standards)

### frontend-engineer

- **Primary** (orchestrator spawns frontend-engineer for these via the same Build/Refactor skills the software-engineer uses, but in UI slices):
  - `build-implementation` (`agent: software-engineer` in frontmatter; orchestrator dispatch table routes UI slices to frontend-engineer — `subagent_type: "frontend-engineer"` appears in skill body and dispatch)
  - `refactor` (orchestrator routes UI refactors to frontend-engineer; `parent: software-engineer` inheritance)
  - `creative-direction` (`agent: frontend-engineer`)
  - `design-system-init` (`agent: frontend-engineer`)
- **Secondary**:
  - `react-native-patterns` (referenced by name in orchestrator UI-slice spawn prompts and by `agents/frontend-engineer.md` body)
  - `web-frontend-patterns` (parallel reference for web stacks)
  - `tool-synthesis` (`agents/frontend-engineer.md` § Tool Synthesis explicitly authorises invocation)
  - `design-qc` (Final-Gate visual QA produced by qa-engineer; frontend-engineer reads the report on CHANGES_REQUESTED)
  - `bug-fix` (per-behaviour TDD for UI bugs)

### infrastructure-engineer

- **Primary**:
  - `infra-scaffold` (`agent: infrastructure-engineer`)
  - `deploy` (`agent: infrastructure-engineer`)
  - `deployment-verification` (`agent: infrastructure-engineer`)
  - `observability-setup` (`agent: infrastructure-engineer`)
  - `microservices-scaffold` (`agent: infrastructure-engineer`)
  - `cross-service-pipeline` (`agent: infrastructure-engineer`)
  - `project-setup` (`agent: infrastructure-engineer`)
  - `harness-config` (`subagent_type: "infrastructure-engineer"` in skill body — the harness-change delegate)
- **Secondary**:
  - `greenfield-scaffold` (orchestrator spawns infrastructure-engineer twice during greenfield — DevX/infra phases)
  - `build-implementation` (infrastructure-engineer is a write-capable role and follows the same ATDD cycle for infra code)

### patch-critic

- **Primary**:
  - `patch-critique` (`agent: patch-critic`; `subagent_type: "patch-critic"` in skill body)
- **Secondary**: _(none documented)_ — patch-critic operates strictly on the diff + test results the orchestrator hands it. It does NOT consult `code-review` or `security-review` (those gates ran upstream and patch-critic's rubric is intentionally non-overlapping).

### planning-agent

- **Primary**:
  - `continuous-planning` (`agent: planning-agent`; `subagent_type: "planning-agent"` in orchestrator dispatch)
- **Secondary**: _(none)_ — planning-agent's edit scope is locked to `pipeline-state/*-plan.md` per `agents/planning-agent.md` § Edit Scope Guard. It does not invoke or read other skills.

### product-reviewer

- **Primary**:
  - `product-acceptance` (`agent: product-reviewer`; `subagent_type: "product-reviewer"` in skill body and orchestrator dispatch)
- **Secondary**:
  - `design-qc` (Final-Gate parallel skill; product-reviewer consumes the Design-QC screenshots + evaluation report per `agents/product-reviewer.md` § 2b. Visual Design Evaluation)
  - `verify` (Final-Gate parallel; product-reviewer must acknowledge `VERIFIED_WITH_SKIP` per `skills/verify/SKILL.md` line 117/130)
  - `plan-self-validation` (challenger-team variant; product-reviewer is the heavy challenger when `critical OR Budget >= 7` per dispatch)

### qa-engineer

- **Primary**:
  - `qa-test-strategy` (`agent: qa-engineer`; `subagent_type: "qa-engineer"` in skill body and orchestrator dispatch)
  - `verify` (orchestrator spawns `qa-engineer` for `/verify` per `parallel-dispatch-details.md` line 484, even though the skill frontmatter still reads `agent: software-engineer` — see Validation Notes)
  - `load-test` (`agent: qa-engineer`)
  - `design-qc` (`agent: qa-engineer`)
- **Secondary**:
  - `react-native-patterns` (qa-test-strategy body line 47: "follow patterns in ~/.claude/skills/react-native-patterns/SKILL.md" for Maestro flows)
  - `build-implementation` (Plan-phase contribution: qa-engineer authors the per-AC failing-test stub list alongside architect — see `agents/qa-engineer.md` § Three-Phase Model)
  - `bug-fix` (per-behaviour TDD applies when filling test gaps that exposed a bug)

### security-engineer

- **Primary**:
  - `security-review` (`agent: security-engineer`; `subagent_type: "security-engineer"` in skill body and orchestrator dispatch)
- **Secondary**:
  - `react-native-patterns` (orchestrator spawn prompt pairs it: "Also read ~/.claude/skills/react-native-patterns/SKILL.md for tech-specific guidance")
  - `web-frontend-patterns` (parallel reference for web stacks)
  - `code-review` (run in parallel; findings are consolidated)
  - Trail-of-Bits Skill plugins (`/static-analysis:semgrep`, `/differential-review:diff-review`, `/supply-chain-risk-auditor:supply-chain-risk-auditor`, `/sharp-edges:sharp-edges`) — security-engineer's `tools:` list grants `Skill`. These are external plugins, NOT under `~/.claude/skills/` — so they do not appear in the inventory above.

### session-memory-updater

- **Primary**: _(no skill)_ — session-memory-updater is dispatched without a skill file. Its full procedure is in `agents/session-memory-updater.md` and the orchestrator spawn prompt (notes path + curated facts).
- **Secondary**: _(none)_ — narrow, single-purpose agent; only Read/Edit on the notes file.

### software-engineer

- **Primary**:
  - `build-implementation` (`agent: software-engineer`; `subagent_type: "software-engineer"` in orchestrator dispatch and skill body)
  - `refactor` (`agent: software-engineer`)
  - `bug-fix` (`agent: software-engineer`)
  - `polish` (`agent: software-engineer`, model: haiku — same role, downgraded model for mechanical cleanup)
  - `pr-creation` (`agent: software-engineer`)
  - `tool-synthesis` (`agent: software-engineer`)
  - `module-extraction` (`agent: software-engineer`)
  - `service-extraction` (`agent: software-engineer`)
  - `bff-scaffold` (`agent: software-engineer`)
  - `voice-scaffold` (`agent: software-engineer`)
  - `api-scaffold` (`agent: software-engineer`)
  - `internal-eval` (`agent: software-engineer`)
- **Secondary**:
  - `react-native-patterns` (orchestrator spawn prompts for UI slices that route to software-engineer when no frontend-engineer is staffed)
  - `web-frontend-patterns` (same)
  - `verify` (build agent must produce evidence for verify; references `skills/verify/SKILL.md` for the mutation-fallback procedure per `build-implementation/SKILL.md` line 67)
  - `qa-test-strategy` (Plan-phase: software-engineer is the heavy-team challenger when `critical OR Budget >= 7`; reads the qa stub-list contract)
  - `plan-self-validation` (challenger-team variant; software-engineer is the heavy challenger alongside product-reviewer)
  - `greenfield-scaffold` (spawned during seed-data phase per dispatch)

## Matrix — Skill-Keyed Reverse Index

For each skill, the agent the orchestrator dispatches (PRIMARY column) and the agents that read it as context (SECONDARY column).

| Skill | Primary agent | Secondary agents |
|-------|---------------|------------------|
| api-scaffold | software-engineer | — |
| batch-pipeline | (orchestrator-only) | — |
| bff-scaffold | software-engineer | — |
| bug-fix | software-engineer | fix-engineer, frontend-engineer, qa-engineer |
| build-implementation | software-engineer (frontend-engineer for UI slices, infrastructure-engineer for infra slices, database-engineer for schema slices) | — |
| capture | (memory infrastructure, no agent) | — |
| code-review | code-reviewer | fix-engineer, security-engineer (parallel) |
| continuous-planning | planning-agent | architect (re-reads on revision) |
| creative-direction | frontend-engineer | — |
| cross-service-pipeline | infrastructure-engineer | — |
| db-migration | database-engineer | — |
| debug | (orchestrator-only utility) | — |
| debug-trace | (orchestrator-only utility) | — |
| deploy | infrastructure-engineer | — |
| deployment-verification | infrastructure-engineer | — |
| design-qc | qa-engineer | frontend-engineer, product-reviewer |
| design-system-init | frontend-engineer | — |
| embedder | (recall/memory infrastructure) | — |
| epic-breakdown | architect | — |
| estimation | architect | — |
| eval-model-effectiveness | (orchestrator-only, advisory) | — |
| forensics | (orchestrator-only utility) | — |
| greenfield-scaffold | (orchestrator dispatches multiple roles) | architect, infrastructure-engineer, software-engineer, frontend-engineer |
| harness-audit | (orchestrator-only utility) | — |
| harness-config | infrastructure-engineer | — |
| health-scan | (orchestrator-only utility) | — |
| infra-scaffold | infrastructure-engineer | — |
| intake | (orchestrator-only) | architect (reads `## Contracts Touched`) |
| internal-eval | software-engineer | — |
| learn | (orchestrator-only utility) | — |
| load-test | qa-engineer | — |
| mcp_memory | (memory infrastructure, no agent) | — |
| microservices-scaffold | infrastructure-engineer | — |
| module-extraction | software-engineer | — |
| observability-setup | infrastructure-engineer | — |
| patch-critique | patch-critic | fix-engineer (reads finding) |
| pipeline | (orchestrator-only) | — |
| pipeline-resume | (orchestrator-only utility) | — |
| plan-self-validation | architect | software-engineer + product-reviewer (heavy-challenger variant) |
| polish | software-engineer (model: haiku) | — |
| pr-creation | software-engineer | — |
| product-acceptance | product-reviewer | fix-engineer (reads finding) |
| project-setup | infrastructure-engineer | — |
| qa-test-strategy | qa-engineer | fix-engineer (reads GAPS_FOUND) |
| react-native-patterns | (pattern reference, no agent) | software-engineer, frontend-engineer, code-reviewer, security-engineer, qa-engineer |
| recall | (memory infrastructure) | — |
| refactor | software-engineer (frontend-engineer for UI, database-engineer for schema) | — |
| reindex-memory | (orchestrator-only utility) | — |
| security-review | security-engineer | fix-engineer, code-reviewer (parallel) |
| service-extraction | software-engineer | infrastructure-engineer (cross-repo coordination) |
| skill-builder | (orchestrator-only utility) | — |
| story-writing | architect | — |
| tech-spike | architect | — |
| tool-synthesis | software-engineer | frontend-engineer |
| verify | qa-engineer (orchestrator dispatch) — see Validation Notes | software-engineer (reads for evidence), patch-critic (reads mutation report), product-reviewer (acknowledges SKIP) |
| voice-scaffold | software-engineer | — |
| web-frontend-patterns | (pattern reference, no agent) | software-engineer, frontend-engineer, code-reviewer, security-engineer |
| workstream | (orchestrator-only utility) | — |

## Validation notes

The matrix surfaced these inconsistencies between what the orchestrator does and what the skill/agent files declare. They are gaps to fix, not noise.

1. **`skills/verify/SKILL.md` declares `agent: software-engineer`** in its frontmatter, but the orchestrator spawns `qa-engineer` for `/verify` (`orchestrator/parallel-dispatch-details.md` line 484; `agents/qa-engineer.md` § Three-Phase Model explicitly claims Verify as phase 2 of the qa-engineer's role). The skill frontmatter is stale. Recommend updating to `agent: qa-engineer`. Without the fix, anyone reading the skill in isolation would route to the wrong role.
2. **`agents/fix-engineer.md` has no primary skill.** The orchestrator dispatches fix-engineer with a hand-built spawn prompt (cited finding + diff + verdict context), not via a skill file. This is intentional per the agent's design (§ Why Fix-Engineer Is a Distinct Role) — fix-cycle work is inherently bespoke per finding. No file under `skills/` describes the fix-cycle procedure as a reusable skill.
3. **`agents/session-memory-updater.md` has no primary skill.** Same shape as fix-engineer: dispatched with a hand-built spawn prompt (notes path + curated facts) by the orchestrator. The procedure lives entirely in the agent file plus `rules/_detail/autonomous-intelligence.md` § Update Mechanism.
4. **`skills/build-implementation/SKILL.md` declares `agent: software-engineer`**, but in practice the orchestrator routes build-implementation slices to `frontend-engineer` (UI), `database-engineer` (schema), or `infrastructure-engineer` (infra) when the slice's domain matches that role. The skill frontmatter is too narrow — it should likely be `agent: software-engineer | frontend-engineer | database-engineer | infrastructure-engineer` or the field should explicitly note "any write-capable build agent". Today the orchestrator overrides correctly via dispatch logic; the skill frontmatter is informational and not load-bearing for routing.
5. **`skills/refactor/SKILL.md` declares `agent: software-engineer`** with the same caveat as build-implementation — UI refactors route to frontend-engineer, schema refactors to database-engineer.
6. **`security-engineer` has `Skill` in its `tools:` list** to invoke Trail-of-Bits plugins (`/static-analysis:semgrep` etc.), which live OUTSIDE `~/.claude/skills/`. The matrix's "Skills" inventory is bound to `~/.claude/skills/`; ToB plugins are not represented and the cross-reference is implicit only.
7. **`patch-critic` lists no secondary skills** despite being a Final-Gate teammate that runs alongside `verify`, `qa-test-strategy`, and `product-acceptance`. This is correct per its rubric (rubric is intentionally non-overlapping with code-review/security-review/QA), but worth noting because a casual reader might expect `patch-critic` to consume more inputs than the diff + test results.
8. **`planning-agent` has no read-time relationship to any skill except `continuous-planning`.** Its edit scope is locked to `pipeline-state/*-plan.md`. This is the narrowest agent surface in the harness — by design, per `agents/planning-agent.md` § Edit Scope Guard.
9. **Pattern skills (`react-native-patterns`, `web-frontend-patterns`)** have no `agent:` field. They are pure reference skills — the orchestrator's spawn prompts for build, code-review, and security-review pair them in via "Also read ..." instructions (see `orchestrator/parallel-dispatch-details.md` lines 185, 216, 336, 362). Nothing dispatches them on their own.

## How to keep this fresh

Regenerate when ANY of the following change:

- An agent is added or removed under `agents/` (e.g., the addition of `fix-engineer` and `planning-agent` were the most recent agent-team changes).
- A skill is added or removed under `skills/`. Keep the inventory count and reverse index in sync.
- A skill's frontmatter `agent:` field changes — re-read the skill and update both the per-agent and reverse-index sections.
- An orchestrator dispatch pattern changes (e.g., a phase that used to spawn agent X now spawns agent Y). The orchestrator files (`orchestrator/agent-orchestration.md` and `orchestrator/parallel-dispatch-details.md`) are the source of truth for primary cells — re-validate by `grep -n "subagent_type" orchestrator/parallel-dispatch-details.md` after any orchestrator edit.
- The Validation Notes section is reduced. Notes 1, 4, 5 in particular are tracking documented stale frontmatter — fixing the underlying frontmatter would let those notes be removed.

The matrix is a derivation, not a source. Do not edit it without re-running the validation steps; otherwise it drifts from the true agent-skill graph.
