---
name: "Intake"
description: "Entry point for all user requests. Classifies work type (feature, refactor, bug, spike, question), estimates complexity, determines pipeline entry point, and invokes /pipeline. Use when receiving any new task from the user."
model: sonnet
argument-hint: "Feature, bug, or task description"
---

# Task Intake

## What This Skill Does

Entry point for all user work requests. Classifies the work, estimates complexity, and routes to the appropriate pipeline or skill.

## Process

### Step 1: Classify the Work

| Signal | Classification | Entry Point |
|--------|---------------|-------------|
| "Add feature", "Implement", new AC | **Feature** | `/pipeline` → `/build-implementation` |
| "Refactor", "Decompose", "Extract", shape violation | **Refactor** | `/pipeline` → `/refactor` |
| "Bug", "Fix", "Broken", "Error", failing test | **Bug Fix** | `/pipeline` → `/bug-fix` |
| "Spike", "Investigate", "Evaluate", "Research" | **Tech Spike** | `/tech-spike` (no pipeline) |
| "Epic", "Feature set", multiple stories | **Epic** | `/epic-breakdown` → `/pipeline` per story |
| Question, "How does", "Explain", "What is" | **Question** | Answer directly (no pipeline) |
| "Set up", new repo, no CLAUDE.md | **Project Setup** | `/project-setup` → Plan phase |
| "API", "endpoint", "resource" (new API) | **Feature + Scaffold** | `/pipeline` → `/api-scaffold` → `/build-implementation` |
| "Migration", "schema", "add column" | **Feature + Scaffold** | `/pipeline` → `/db-migration` → `/build-implementation` |
| "Docker", "CI/CD", "deploy", "infra" | **Infrastructure** | `/pipeline` → `/infra-scaffold` |
| "Extract", "split out", "own repo", "separate service" | **Service Extraction** | `/pipeline` → `/service-extraction` |
| "Logging", "monitoring", "observability" | **Infrastructure** | `/pipeline` → `/observability-setup` |

### Step 2: Complexity Budget (MANDATORY — score before routing)

Score each dimension 1-3 and sum. This is not optional — routing depends on the total.

| Dimension | 1 (Low) | 2 (Medium) | 3 (High) |
|-----------|---------|-----------|----------|
| **Scope** (files to touch) | 1-3 files | 4-10 files | 11+ files |
| **Ambiguity** (requirement clarity) | Fully specified ACs | Interpretation needed | Discovery required |
| **Context Pressure** (codebase knowledge) | Single module | Cross-module | System-wide |
| **Novelty** (precedent exists?) | Pattern to follow | Partial precedent | Greenfield |
| **Coordination** (cross-cutting?) | Isolated | 2-3 concerns | Auth + data + UI + infra |

**Thresholds → routing:**

| Budget | Action | Pipeline Scale |
|--------|--------|---------------|
| 5-6 | Execute directly, no planning needed | Micro/Small |
| 7-8 | Compound — plan first, then build | Small/Medium |
| 9-10 | Compound — plan first, then build | Medium |
| 11-12 | Multi-session — break into sub-tasks | Large |
| 13-15 | **Must decompose** before starting — use `/epic-breakdown` | Epic |

**Output the score explicitly:**
```
[Intake] CB Score: Scope=N, Ambiguity=N, Context=N, Novelty=N, Coordination=N → Total=N
[Intake] Routing: [execute directly / plan first / decompose]
```

### Step 3: Pre-flight Check

Before invoking pipeline, verify:
1. `.claude/CLAUDE.md` exists — if not, **automatically invoke `/project-setup` before proceeding**. Do not ask the user — just detect, scaffold, and continue. This includes design system init for frontend projects.
2. Branch is correct (not on main for features/refactors)
3. Working tree is clean (`git status`)
4. Tests pass baseline (`npm test` / equivalent)

### Step 4: Route to Pipeline

Output the classification and route:

```
[Intake] Classification: [type]
[Intake] Complexity: [small/medium/large] ([N] files, [coverage], [scope])
[Intake] Entry skill: /[skill-name]
[Intake] Pipeline phases: [list]
```

Then invoke `/pipeline` (or the appropriate skill for non-pipeline work).

## Phase Output

```
Verdict: ROUTED (informational — no gate)
Next: /pipeline, /tech-spike, /epic-breakdown, or direct answer
Classification: [feature/refactor/bug/spike/epic/question/setup]
Complexity: [small/medium/large]
```
