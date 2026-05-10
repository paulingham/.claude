---
task_id: v2-dup-id
schema_version: 2
dag: true
phase: plan
---

## Context

Duplicate IDs: two slices with id `a`.

## Slices

```yaml
slices:
  - id: a
    depends-on: []
    description: First a.
  - id: a
    depends-on: []
    description: Second a — collision.
```
