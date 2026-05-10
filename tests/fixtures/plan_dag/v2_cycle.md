---
task_id: v2-cycle
schema_version: 2
dag: true
phase: plan
---

## Context

Cycle: A -> B -> A. Validation must fail with `cycle:` token.

## Slices

```yaml
slices:
  - id: a
    depends-on: [b]
    description: A depends on B.
  - id: b
    depends-on: [a]
    description: B depends on A — closes the cycle.
```
