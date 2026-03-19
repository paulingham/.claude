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

### Step 2: Quick Complexity Assessment

Before starting, estimate scope:

| Check | How | Result |
|-------|-----|--------|
| Files affected | `grep` for related code, count files | 1 (micro), 1-3 (small), 4-10 (medium), 11+ (large) |
| Lines changed | Estimate delta | <5 (micro), 5-50 (small), 50+ (medium/large) |
| Behavior change | Does it change observable behavior? | No (micro), Yes (small+) |
| Test coverage | Check `__tests__/` for existing tests | Covered / Partial / None |
| Cross-cutting | Does it span multiple directories? | Isolated / Cross-module / System-wide |

**Routing by complexity:**
- **Micro** (1 file, <5 lines changed, no behavior change): `/pipeline` with Build + Review + Ship only
- **Small** (1-3 files, isolated): `/pipeline` with Build + Review + Verify + Ship
- **Medium** (4-10 files, cross-module): `/pipeline` with full phases
- **Large** (11+ files, system-wide): `/epic-breakdown` first, then `/pipeline` per story

### Step 3: Pre-flight Check

Before invoking pipeline, verify:
1. `.claude/CLAUDE.md` exists (if not: `/project-setup`)
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
