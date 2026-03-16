---
name: "Estimation"
description: "Complexity Budget estimation for sizing stories. Scores 5 dimensions (scope, ambiguity, context pressure, novelty, coordination) 1-3 each, with Fibonacci mapping for human teams. Use during epic breakdown and story estimation."
---

# Complexity Budget Estimation

## What This Skill Does

Sizes stories using a 5-dimension Complexity Budget that reflects AI-native work dimensions, with Fibonacci mapping for backward compatibility.

## Complexity Budget

Score each dimension 1-3:

| Dimension | 1 (Low) | 2 (Medium) | 3 (High) |
|-----------|---------|-----------|----------|
| **Scope** (files to touch) | 1-3 files | 4-10 files | 11+ files |
| **Ambiguity** (requirement clarity) | Fully specified ACs | Interpretation needed | Discovery required |
| **Context Pressure** (codebase knowledge) | Single module | Cross-module | System-wide |
| **Novelty** (precedent exists?) | Pattern to follow | Partial precedent | Greenfield |
| **Coordination** (cross-cutting?) | Isolated | 2-3 concerns | Auth + data + UI + infra |

## Thresholds

| Budget | Action | Fibonacci |
|--------|--------|-----------|
| 5-6 | Single task, execute directly | 1-2 pts |
| 7-8 | Compound task, plan first | 3-5 pts |
| 9-10 | Compound task, plan first | 8 pts |
| 11-12 | Multi-session, break into sub-tasks | 13 pts |
| 13-15 | Must decompose before starting | 21+ pts (must split) |

## Estimation Guidelines

### What to Consider
- Implementation complexity (code changes)
- Testing effort (unit, integration, E2E)
- Infrastructure changes (CI/CD, deployment)
- Data migration or schema changes
- External dependencies (APIs, services)
- Risk and unknowns

### When to Re-Estimate
- Requirements change significantly
- Discovery reveals hidden complexity
- Dependencies shift or new blockers emerge

### Anti-Patterns
- Never estimate to precision — use the budget, not hours
- Never pad estimates for "safety" — surface uncertainty instead
- Never split into sub-tasks to reduce per-task size artificially
- Budget 13-15 MUST be decomposed before starting

## Output Format

```markdown
### Complexity Budget: [total] / 15

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Scope | X | [reason] |
| Ambiguity | X | [reason] |
| Context Pressure | X | [reason] |
| Novelty | X | [reason] |
| Coordination | X | [reason] |

**Fibonacci mapping**: [X] points
**Action**: [execute / plan first / break into sub-tasks / must decompose]
```

```json
{
  "stories_created": [
    {"title": "...", "complexity_budget": 7, "story_points": 5, "priority": "high"},
    {"title": "...", "complexity_budget": 5, "story_points": 2, "priority": "medium"}
  ],
  "engineering_estimate": "Total: 12 budget across 2 stories (7 Fibonacci points)"
}
```
