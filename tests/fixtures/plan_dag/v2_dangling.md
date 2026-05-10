---
task_id: v2-dangling
schema_version: 2
dag: true
phase: plan
---

## Context

Dangling dep: A depends on `ghost`, which is not declared.

## Slices

```yaml
slices:
  - id: a
    depends-on: [ghost]
    description: References an undeclared id.
```
