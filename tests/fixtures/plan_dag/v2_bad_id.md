---
task_id: v2-bad-id
schema_version: 2
dag: true
phase: plan
---

## Context

Bad ID format: `BadID_123` violates kebab-case regex.

## Slices

```yaml
slices:
  - id: BadID_123
    depends-on: []
    description: Snake_case + uppercase, not kebab.
```
