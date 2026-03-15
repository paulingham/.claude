---
name: "Estimation"
description: "Fibonacci estimation guidance for sizing epics and stories. Includes scale reference, complexity factors, and anti-patterns. Use during epic breakdown and story estimation."
---

# Fibonacci Estimation Guide

## Scale Reference

| Points | Effort | Uncertainty | Duration Hint |
|--------|--------|------------|---------------|
| **1** | Trivial | None | Hours |
| **2** | Simple | Minimal | Half day |
| **3** | Standard | Low | 1 day |
| **5** | Moderate | Some | 2-3 days |
| **8** | Complex | Moderate | 3-5 days |
| **13** | Very complex | High | 1-2 weeks |
| **21** | Epic-sized | Very high | Must split |

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
- Team velocity data shows consistent miss

### Estimation Anti-Patterns
- Never estimate to precision (use Fibonacci, not hours)
- Never pad estimates for "safety" - surface uncertainty instead
- Never split into sub-tasks to reduce per-task size artificially
- If story is 21+ points, it MUST be broken down further

## Complexity Factors Checklist

- [ ] New technology or pattern? (+1 level)
- [ ] Cross-service integration? (+1 level)
- [ ] Database migration? (+1 level)
- [ ] External API dependency? (+1 level)
- [ ] Security-sensitive? (+1 level)
- [ ] Performance-critical? (+1 level)

## Output Format

Include `story_points` in estimation output:

```json
{
  "stories_created": [
    {"title": "...", "story_points": 5, "priority": "high"},
    {"title": "...", "story_points": 3, "priority": "medium"}
  ],
  "engineering_estimate": "Total: 34 story points across 8 stories"
}
```
