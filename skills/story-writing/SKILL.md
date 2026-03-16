---
name: "Story Writing"
description: "Write a single well-formed user story with persona, Given/When/Then acceptance criteria, error paths, and Complexity Budget estimate. Use when creating individual stories."
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

| Dimension | 1 (Low) | 2 (Medium) | 3 (High) |
|-----------|---------|-----------|----------|
| **Scope** | 1-3 files | 4-10 files | 11+ files |
| **Ambiguity** | Fully specified ACs | Interpretation needed | Discovery required |
| **Context Pressure** | Single module | Cross-module | System-wide |
| **Novelty** | Pattern to follow | Partial precedent | Greenfield |
| **Coordination** | Isolated | 2-3 concerns | Auth + data + UI + infra |

### 5. Check Anti-Patterns

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
```
