---
name: "estimation"
description: "Use when sizing stories with the Complexity Budget. Scores 5 dimensions (scope, ambiguity, context pressure, novelty, coordination) 1-3 each. Output is the raw budget total and the routing action — no Fibonacci/story-points translation."
context: fork
agent: architect
---

# Complexity Budget Estimation

## What This Skill Does

Sizes stories using a 5-dimension Complexity Budget that drives pipeline routing decisions (`bestofn`, `critical`, team-vs-subagent, decompose-or-execute). The output is the raw budget total and the action threshold — no Fibonacci translation, no story-points field.

## Complexity Budget

See the Complexity Budget table in `rules/_detail/operational-protocol.md` for the 5-dimension scoring matrix and thresholds.

Score each dimension 1-3. Total budget determines action.

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
- Never estimate to precision — use the budget, not hours or points
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

**Action**: [execute / plan first / break into sub-tasks / must decompose]
```

```json
{
  "stories_created": [
    {"title": "...", "complexity_budget": 7, "priority": "high"},
    {"title": "...", "complexity_budget": 5, "priority": "medium"}
  ],
  "engineering_estimate": "Total: 12 budget across 2 stories"
}
```

## Phase Output

```
Verdict: ESTIMATED (informational — no gate)
Next: If budget ≤ 10 → /build-implementation
      If budget 11-12 → /epic-breakdown to decompose further
      If budget 13-15 → MUST decompose before proceeding
Artifacts: [complexity budget scores, action recommendation]
```
