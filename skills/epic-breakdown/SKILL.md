---
name: "Epic Breakdown"
description: "Decompose an epic into estimated stories with acceptance criteria. Orchestrates architect for design, estimation for sizing, and outputs structured stories. Use when breaking down epics or features into implementable stories."
---

# Epic Breakdown

## What This Skill Does

Decomposes an epic or feature request into deployable vertical slices — each with acceptance criteria, estimation, and implementation notes.

## Process

### 1. Understand the Epic
- Read the epic description and any linked requirements
- Identify the core user problem being solved
- Determine success metrics and business value

### 2. Identify User Personas
- Who are the distinct user roles affected?
- What is each persona's primary goal?
- What are the happy path and error scenarios per persona?

### 3. Slice into Stories
Apply elephant carpaccio — the thinnest possible slices:
- Each story delivers end-to-end functionality (DB + API + UI + tests)
- Each story is independently deployable and testable
- Each story delivers observable user value
- If a story has a budget of 13-15, it MUST be decomposed further

### 4. Write Acceptance Criteria
For each story:
- **Given/When/Then** format for each AC
- At least one happy path and one error path
- Clear, testable, and unambiguous

### 5. Estimate Stories

Use Complexity Budget — score each dimension 1-3:

| Dimension | 1 (Low) | 2 (Medium) | 3 (High) |
|-----------|---------|-----------|----------|
| **Scope** | 1-3 files | 4-10 files | 11+ files |
| **Ambiguity** | Fully specified | Interpretation needed | Discovery required |
| **Context Pressure** | Single module | Cross-module | System-wide |
| **Novelty** | Pattern exists | Partial precedent | Greenfield |
| **Coordination** | Isolated | 2-3 concerns | Auth + data + UI + infra |

**Thresholds**: 5-6 execute, 7-10 plan first, 11-12 break down, 13-15 must decompose.
**Fibonacci mapping**: 5-6→1-2pts, 7-8→3-5pts, 9-10→8pts, 11-12→13pts, 13-15→21+ (must split).

### 6. Order by Priority
- Dependencies first (data model → API → UI)
- Highest business value within each dependency tier
- Risk-reduction stories early

## Output Format

```markdown
## Epic: [Epic Title]

### Summary
[2-3 sentences describing the epic and its business value]

### Personas
- **[Persona 1]**: [goal and primary flow]
- **[Persona 2]**: [goal and primary flow]

### Stories

#### Story 1: [Title] — [X] points
**Priority**: High / Medium / Low

**Acceptance Criteria**:
- [ ] Given [context], when [action], then [outcome]
- [ ] Given [context], when [error case], then [error handling]

**Notes**: [Implementation hints, dependencies, risks]

---

#### Story 2: [Title] — [X] points
...

### Summary
- **Total stories**: N
- **Total points**: X
- **Estimated sprints**: Y (at velocity Z)
```

## Anti-Patterns
- Never estimate to precision — use the Complexity Budget, not hours
- Never pad estimates — surface uncertainty instead
- Never split into sub-tasks to reduce per-task size artificially
- Never create horizontal slices (all DB, then all API, then all UI)
