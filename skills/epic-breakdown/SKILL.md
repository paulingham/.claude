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

Use the Complexity Budget table in `rules/operational-protocol.md`. Score each dimension 1-3, apply thresholds and Fibonacci mapping.

**Thresholds**: 5-6 execute, 7-10 plan first, 11-12 break down, 13-15 must decompose.

### 6. Order by Priority
- Dependencies first (data model → API → UI)
- Highest business value within each dependency tier
- Risk-reduction stories early

### 7. Identify Parallelizable Stories

For each story, annotate whether it can be built in parallel with other stories:
- **Independent**: No shared files with other stories → can run in parallel worktree
- **Sequential**: Depends on another story's output (shared files, data model) → must wait
- Group independent stories into parallel batches in the output

Add a "### Parallel Batches" section to the output showing which stories can be built simultaneously.

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

## Phase Output

```
Verdict: STORIES_READY (informational — no gate)
Next: /build-implementation (per story, or parallel for independent stories)
      /estimation if sizing not yet done
      /story-writing if individual stories need refinement
Artifacts: [story list with ACs, points, parallel batches]
```
