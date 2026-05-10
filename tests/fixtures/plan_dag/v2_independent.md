---
task_id: v2-independent
schema_version: 2
dag: true
phase: plan
---

## Context

Three independent slices, no edges. All co-runnable in one wave.

## Slices

```yaml
slices:
  - id: a
    depends-on: []
    description: Independent A.
  - id: b
    depends-on: []
    description: Independent B.
  - id: c
    depends-on: []
    description: Independent C.
```
