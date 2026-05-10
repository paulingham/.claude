---
task_id: v2-chain
schema_version: 2
dag: true
phase: plan
---

## Context

Linear chain: A -> B -> C.

## Slices

```yaml
slices:
  - id: a
    depends-on: []
    description: First slice.
  - id: b
    depends-on: [a]
    description: Second; depends on A.
  - id: c
    depends-on: [b]
    description: Third; depends on B.
```

### Slice a

A.

### Slice b

B.

### Slice c

C.
