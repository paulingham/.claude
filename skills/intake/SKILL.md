---
name: "intake"
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

### Step 2b: Exploration Gate (MANDATORY when Ambiguity >= 2)

Before routing to a full pipeline, confirm the approach is validated:

1. **Integration point**: "Where does this render / execute / integrate? Does it replace existing behavior, extend it, or live separately?"
2. **Fidelity**: "Should I build a throwaway prototype first, or go straight to production code?" If prototype → route to `/tech-spike`
3. **External data**: "Do I have the real data structure (API response, HTML, schema), or am I guessing?" If guessing → request it before building
4. **Approach validation**: If multiple implementation approaches exist (e.g., injection vs component, server vs client, sync vs async), confirm the approach with the user before committing

Skip this gate only when Ambiguity = 1 (fully specified ACs with no interpretation needed).

**Why:** Building the wrong approach through a full pipeline wastes more effort than asking 2-3 clarifying questions upfront.

#### Discussion Persistence (MANDATORY when this gate fires)

Create `pipeline-state/{task-id}-discussion.md` to persist the exploration discussion:

```markdown
---
task_id: {task-id}
phase: intake
gate: exploration
ambiguity_score: {N}
timestamp: {ISO 8601}
---

## Discussion: {task summary}

### Questions Asked
| # | Question | Category | User Response | Decision |
|---|----------|----------|---------------|----------|
| 1 | {question} | {integration/fidelity/data/approach} | {response} | {decision made} |

### Decisions Summary
- {Decision 1}: {rationale}

### Impact on Implementation
- Approach: {chosen approach from validation}
- Integration point: {where it fits}
- Data assumptions: {confirmed or external data provided}
```

This file feeds into the architect during the Plan phase and survives context compaction.

### Step 3: Pre-flight Check

Before invoking pipeline, verify and auto-fix:
1. **CLAUDE.md** — if not present, automatically invoke `/project-setup`. Do not ask.
2. **In-progress pipeline** — check `pipeline-state/*-pipeline.md`. If found, automatically invoke `/pipeline-resume` instead of starting a new pipeline. Inform the user: "Found in-progress pipeline [name]. Resuming from [phase]."
3. **Feature branch** — if on `main`/`master` and the work is a feature, refactor, or bug fix: automatically create and switch to a feature branch. Branch name: `feat/[kebab-case-summary]`, `fix/[kebab-case-summary]`, or `refactor/[kebab-case-summary]`. Do not ask — just create it.
4. **Working tree clean** — if uncommitted changes exist, warn the user before proceeding. Do not auto-commit — the user may have in-progress work.
5. **Test runner worktree exclusion** — on first pipeline run in a project, check that the test runner config excludes `.claude/worktrees/`. If not configured, add the exclusion automatically (Jest: `testPathIgnorePatterns`, pytest: `testpaths`, rspec: `--exclude-pattern`).
6. **Baseline tests** — run the project's test command (from CLAUDE.md Commands). If tests fail before we start, warn the user.

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
$ARGUMENTS
