---
name: "Verify"
description: "Structured verification workflow: contract tests, smoke tests, mutation testing. Produces a tiered verification report with VERIFIED/UNVERIFIED verdict. Use after implementation to prove correctness beyond passing tests."
---

# Verification Workflow

## What This Skill Does

Proves a feature works correctly beyond just passing tests. Runs three verification tiers and produces a verdict.

## Verification Tiers

| Feature Type | Tier 1 (Contract) | Tier 2 (Smoke) | Tier 3 (Mutation) |
|-------------|-------------------|----------------|-------------------|
| Backend API | Hit real endpoint, verify response shape | curl + DB state check + log check | Mutate handler logic |
| Frontend | Props match API response shape | Playwright/browser screenshot | Mutate component logic |
| Database | Schema constraint tests | Migrate up+down, verify integrity | N/A |
| Infrastructure | Health endpoint responds | Readiness probe passes | N/A |

## Process

### 1. Identify Feature Type

Detect from changed files: API routes → Backend API, components → Frontend, migrations → Database, Dockerfile/CI → Infrastructure.

### 2. Run Tier 1: Contract Tests

- Test real boundaries (API responses, database constraints, service contracts)
- Verify response shapes match expected contracts
- For APIs: actual HTTP requests, not mocked responses

### 3. Run Tier 2: Smoke Tests

- Exercise the feature end-to-end in the real environment
- Verify side effects: database state changes, log entries, events emitted
- For UI: capture screenshots of key states

### 4. Run Tier 3: Mutation Testing (where applicable)

- Mutate logic in changed files
- Verify existing tests catch the mutations
- Focus on business logic, skip trivial mutations

### 5. Produce Verification Report

## Output Format

```markdown
## Verification Report: [Feature]

### Feature Type: [Backend API / Frontend / Database / Infrastructure]

### Tier 1: Contract Tests
- **Status**: PASS / FAIL
- **Evidence**: [actual responses, constraint results]

### Tier 2: Smoke Tests
- **Status**: PASS / FAIL
- **Evidence**: [curl output, DB queries, screenshots]

### Tier 3: Mutation Testing
- **Status**: PASS / FAIL / N/A
- **Score**: [X/Y mutations caught]
- **Uncaught**: [list of surviving mutations]

### Verdict: VERIFIED / UNVERIFIED
[If UNVERIFIED: which tier failed and why]
```
