---
id: instinct-bash-rematch-reindex
confidence: 0.3
domain: hooks
scope: project
roles: [software-engineer, code-reviewer]
source: build-feedback
created: 2026-06-04T00:00:00Z
evidence_count: 1
last_seen: 2026-06-04T11:27:30Z
---

## Pattern

When adding a new capture group (including alternation groups like `(bash|sh)`) to a bash regex, all downstream `${BASH_REMATCH[N]}` references MUST be reindexed — every group, including non-capturing-looking alternations, shifts subsequent indices by one.

```bash
# Before: [[ "$line" =~ ^([0-9]+):[[:space:]](.+)$ ]]
# BASH_REMATCH[1]=number  BASH_REMATCH[2]=text

# After adding alternation group:
# [[ "$line" =~ ^(bash|sh)[[:space:]]([0-9]+):[[:space:]](.+)$ ]]
# BASH_REMATCH[1]=interpreter  BASH_REMATCH[2]=number  BASH_REMATCH[3]=text
# Failing to reindex silently reads stale/wrong data, no error raised
```

## Why

guard-hardening-telemetry-fixes build (2026-06-04): adding a `(bash|sh)` alternation group to a hook test regex caused downstream `BASH_REMATCH` reads to reference wrong indices. Tests caught the regression only because new test cases covered the new alternation form — existing tests passed because their input didn't match the new group. Bash does not raise an error for out-of-bounds `BASH_REMATCH` reads; they silently return empty string.

## How to Apply

- **Build**: after adding or removing any capture group in a regex, grep for all `BASH_REMATCH` uses in the same function/block and recount from `[1]`
- **Code-review**: when a regex diff adds `(...)` — including alternation `(a|b)` — require a side-by-side check of `BASH_REMATCH` index references
- **Testing**: test cases MUST cover the new alternation forms, not just the original form; absence of new test cases for new alternation branches is a review flag
