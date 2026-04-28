---
name: "story-writing"
description: "Write a single well-formed user story with persona, Given/When/Then acceptance criteria, error paths, and Complexity Budget estimate. Use when creating individual stories."
context: fork
agent: architect
model: sonnet
---

# Story Writing

## What This Skill Does

Writes a single, well-formed user story with acceptance criteria and estimation.

## Process

### 1. Identify Persona

- Who is the user? (role, goal, context)
- What problem are they solving?
- What does success look like?

### 2. Write Story Statement

**As a** [persona], **I want to** [action], **so that** [value].

### 3. Define Acceptance Criteria

For each criterion, use Given/When/Then:
- At least one happy path
- At least one error path per AC
- Edge cases where applicable

### 4. Estimate with Complexity Budget

See the Complexity Budget table in `rules/operational-protocol.md`. Score each dimension 1-3.

### 5. Failing Test Stubs (per AC)

For every AC, write a one-line test stub the build agent will use as the contract for the batched-RED step. Each stub names: test file path, test name, assertion intent. The build agent halts if any AC has no stub — no implementation begins without a complete stub list.

| AC | Test File | Test Name | Assertion Intent |
|----|-----------|-----------|------------------|
| AC1 | `tests/test_<feature>.py` | `test_<behavior>` | <one sentence: what the test asserts> |

Stubs are dependency-ordered: foundational ACs first, composed ACs last. The build agent implements in this order.

### 6. Check Anti-Patterns

Reject if:
- Horizontal slice (all DB, then all API, then all UI)
- Vague ACs ("should work correctly")
- Missing error paths
- No clear persona or value statement
- Cannot be independently deployed and tested

## Output Format

```markdown
## Story: [Title]

**As a** [persona], **I want to** [action], **so that** [value].

### Acceptance Criteria
- [ ] **Given** [context], **when** [action], **then** [outcome]
- [ ] **Given** [context], **when** [error case], **then** [error handling]

### Complexity Budget: [total] / 15

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Scope | X | [reason] |
| Ambiguity | X | [reason] |
| Context Pressure | X | [reason] |
| Novelty | X | [reason] |
| Coordination | X | [reason] |

**Fibonacci mapping**: [X] points

### Notes
[Implementation hints, dependencies, risks]

### Failing Test Stubs (per AC)

| AC | Test File | Test Name | Assertion Intent |
|----|-----------|-----------|------------------|
| AC1 | tests/test_<feature>.py | test_<behavior> | <assertion intent> |
```

## Phase Output

```
Verdict: STORY_READY (informational — no gate)
Next: /estimation if sizing needed, then /build-implementation
Artifacts: [story with ACs, complexity budget, notes]
```
