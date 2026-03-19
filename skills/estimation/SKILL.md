---
name: "Estimation"
description: "Complexity Budget estimation for sizing stories. Scores 5 dimensions (scope, ambiguity, context pressure, novelty, coordination) 1-3 each, with Fibonacci mapping for human teams. Use during epic breakdown and story estimation."
---

# Complexity Budget Estimation

## What This Skill Does

Sizes stories using a 5-dimension Complexity Budget that reflects AI-native work dimensions, with Fibonacci mapping for backward compatibility.

## Complexity Budget

See the Complexity Budget table in `rules/operational-protocol.md` for the 5-dimension scoring matrix and thresholds.

Score each dimension 1-3. Total budget determines action and Fibonacci mapping.

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

## Phase Output

```
Verdict: ESTIMATED (informational — no gate)
Next: If budget ≤ 10 → /build-implementation
      If budget 11-12 → /epic-breakdown to decompose further
      If budget 13-15 → MUST decompose before proceeding
Artifacts: [complexity budget scores, Fibonacci mapping, action recommendation]
```
