---
task_id: v2-self-dep
schema_version: 2
dag: true
phase: plan
---

## Context

Self-dependency: A -> A.

## Slices

```yaml
slices:
  - id: a
    depends-on: [a]
    description: Self-loop.
```
