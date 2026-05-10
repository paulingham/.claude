---
task_id: v2-single
schema_version: 2
dag: true
phase: plan
---

## Context

Single-slice v2 fixture for plan_dag_resolver tests.

## Slices

```yaml
slices:
  - id: only
    depends-on: []
    description: The only slice in this plan.
```

### Slice only

Single root, no dependencies.
