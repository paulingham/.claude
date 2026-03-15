---
name: "Bug Fix"
description: "Root cause analysis workflow with incremental TDD for bug fixes. Covers reproduce, analyze, regression test, fix, verify, and prevent. Use when fixing bugs to ensure proper methodology."
---

# Bug Fix Workflow

Follow root cause analysis methodology with incremental TDD.

## Process

1. **Reproduce**: Write a single failing test that demonstrates the bug
2. **Root Cause Analysis**: Trace the issue to the exact source
3. **Regression Test**: Ensure the failing test covers the exact bug scenario
4. **Fix**: Write minimum code to make the test pass
5. **Verify**: All tests pass including new regression test
6. **Prevention**: Apply design patterns to prevent recurrence
7. **PR**: Create PR with bug description, root cause, and fix

## Context

Gather state before starting:

```bash
# Recent failures and changes
git status
git log --oneline -5
```

## Root Cause Analysis Template

- **Symptom**: What the user sees
- **Expected Behavior**: What should happen
- **Actual Behavior**: What actually happens
- **Root Cause**: Why it happens (trace to exact file:line)
- **Fix**: What changes resolve it
- **Prevention**: How to prevent recurrence (pattern, validation, test)

## Fix Verification Checklist

- [ ] Failing test written BEFORE fix
- [ ] Fix is minimal - only what's needed
- [ ] All existing tests still pass
- [ ] No regressions introduced
- [ ] Root cause documented in PR description
- [ ] Design pattern applied if recurrence risk exists

## Design Patterns for Prevention

- **Guard clauses**: Prevent invalid state from propagating
- **Value Objects**: Ensure data integrity at construction
- **Strategy**: Replace fragile conditionals with polymorphism
- **Observer**: Decouple event handling to prevent cascading failures

## Multi-Language Debugging

- **Ruby**: Use `binding.irb`, trace with `caller`, check logs
- **JavaScript**: Use `debugger`, check browser console, trace async flow
- **Python**: Use `breakpoint()`, trace with `traceback`, check stack frames

## Async Debugging

- Trace promise chains: check for missing `.catch()` or unhandled rejection handlers
- Verify async/await error boundaries: every `await` should be in a try/catch or the function should propagate
- Check for fire-and-forget patterns: unresolved promises that silently fail
- Verify callback ordering: ensure async operations complete before dependent code runs
- Check event loop blocking: long synchronous operations preventing async callbacks

## Race Condition Diagnosis

- Check for shared mutable state accessed by concurrent processes/threads/requests
- Verify database transactions wrap read-modify-write sequences
- Look for TOCTOU (time-of-check-time-of-use): data changing between validation and action
- Check for missing locks: concurrent job executions modifying same records
- Verify optimistic locking for concurrent updates
- Test with concurrent requests: use threading/async in tests to reproduce

## Database Debugging

- Run `EXPLAIN ANALYZE` on slow queries to identify missing indexes or full table scans
- Check for N+1: enable query logging, count queries per request
- Verify transaction isolation level matches requirements
- Check for deadlocks: review lock ordering, minimize transaction scope
- Verify connection pool size: check for pool exhaustion under load

## State Management Bugs

- Stale closures: check useEffect/useCallback dependency arrays for missing variables
- Missing dependency arrays: empty `[]` in useEffect when deps change causes stale reads
- Incorrect cache invalidation: mutations not invalidating affected queries
- Race conditions in React: state updates from unmounted components (missing cleanup in useEffect)
- Zustand selector issues: using whole store object instead of selecting specific slices

## Log Analysis

- Structured log queries: filter by correlation_id to trace a single request across services
- Error clustering: group errors by error class and message to find the most common
- Timeline reconstruction: sort logs by timestamp with correlation_id to see exact sequence
- Compare before/after: check logs from when the feature worked vs when it broke
- Check for silent swallowing: search for empty `rescue`/`catch` blocks that hide errors
