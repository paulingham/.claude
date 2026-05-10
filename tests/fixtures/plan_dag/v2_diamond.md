---
task_id: v2-diamond
schema_version: 2
dag: true
phase: plan
---

## Context

Diamond v2 fixture: R -> {A, B} -> D.

## Slices

```yaml
slices:
  - id: r
    depends-on: []
    description: Root slice.
  - id: a
    depends-on: [r]
    description: Branch A; depends on R.
  - id: b
    depends-on: [r]
    description: Branch B; depends on R.
  - id: d
    depends-on: [a, b]
    description: Sink; depends on A and B.
```

### Slice r

Root.

### Slice a

Branch A.

### Slice b

Branch B.

### Slice d

Sink — depends on both branches.
