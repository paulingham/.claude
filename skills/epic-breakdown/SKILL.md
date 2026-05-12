---
name: "epic-breakdown"
description: "Decompose an epic into estimated stories with acceptance criteria. Orchestrates architect for design, estimation for sizing, and outputs structured stories. Use when breaking down epics or features into implementable stories."
context: fork
agent: architect
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

#### Elephant Carpaccio Decomposition Procedure

The goal is the THINNEST possible vertical slices — each deployable, each delivering
observable user value. Most developers slice 3-5 times; aim for 10-20 slices.

**Step 1: List the Cutting Dimensions**
Every feature can be cut along these universal axes:
- **Data scope**: All fields → subset of fields → single field → hardcoded
- **User type**: All personas → single persona → single permission level
- **Workflow step**: Full flow → single step → happy path only → read-only
- **Error handling**: All errors → no error handling (happy path ships first)
- **Volume**: Batch/collection → single item
- **Fidelity**: Full production quality → minimal viable UI → CLI/stub output
- **Integration**: Real dependency → fake/stub → in-memory
- **Input source**: All inputs → single input type → hardcoded input
- **Output target**: All consumers → single consumer → log output

Not all dimensions apply to every feature. Pick the 3-4 that create
the most meaningful cuts for THIS feature.

**Step 2: Apply Cuts Recursively**
1. Take the full feature
2. Pick the dimension that removes the most scope while keeping user value
3. Cut — you now have two halves. Take the smaller half.
4. Can it be cut again on a DIFFERENT dimension? Cut again.
5. Stop when the slice is ≤ 5 Complexity Budget points
6. Each slice MUST still be end-to-end (input → logic → output → test)
7. If a slice has no observable user value, it's a horizontal slice — merge it back

**Step 3: Validate Independence for Parallel Dispatch**
For each slice, list the files it will create or modify:
- **Zero file overlap** with other slices → INDEPENDENT (parallel worktree)
- **Any shared file** → SEQUENTIAL (must wait for predecessor)

Group independent slices into parallel batches. This directly feeds
the Parallel Dispatch Protocol for build phase execution.
The thinner the slice, the more likely it's independent.

**Step 4: Order by Dependency + Value**
- Foundation slices first (types, storage, core abstractions)
- High-value slices next (core happy path for primary persona)
- Edge cases, error handling, and secondary personas last
- Within each tier, highest business value first

**The Test: Is This Slice Thin Enough?**
- Can you describe what the user observes in ONE sentence?
- Can you build it with ≤ 5 files changed?
- Can you demo it to a stakeholder and they say "yes, that works"?
- If no to any: cut thinner.

**Anti-Pattern: Horizontal Slicing**
NEVER slice by architectural layer:
- "Story 1: Build all data models"
- "Story 2: Build all business logic"
- "Story 3: Build all UI"

ALWAYS slice by user-observable behaviour:
- "Story 1: User can see X (read path, end-to-end)"
- "Story 2: User can change X (write path, end-to-end)"
- "Story 3: System handles X failure (error path, end-to-end)"

### 4. Write Acceptance Criteria
For each story:
- **Given/When/Then** format for each AC
- At least one happy path and one error path
- Clear, testable, and unambiguous

### 5. Estimate Stories

Use the Complexity Budget table in `protocols/operational-protocol.md`. Score each dimension 1-3, apply thresholds and Fibonacci mapping.

**Thresholds**: 5-6 execute, 7-10 plan first, 11-12 break down, 13-15 must decompose.

### 6. Order by Priority
- Dependencies first (data model → API → UI)
- Highest business value within each dependency tier
- Risk-reduction stories early

### 6b. Document Alternatives

For the overall approach (not per-story):
1. List at least 2 alternative approaches that were considered
2. For each alternative, document:
   - **Approach**: What would be built differently
   - **Trade-offs**: Advantages and disadvantages vs. the chosen approach
   - **Rejection rationale**: Why this was not selected
3. If genuinely only one viable approach exists, document:
   - Why alternatives are infeasible (technical constraints, time, dependencies)
   - What trade-off within the chosen approach was the hardest decision
4. Alternatives must be genuine — not strawman "do nothing" or "rewrite everything" options

**Output format**:
```markdown
### Alternatives Considered
| Approach | Trade-offs | Rejection Rationale |
|----------|-----------|---------------------|
| {approach 1} | {pros/cons} | {why rejected} |
| {approach 2} | {pros/cons} | {why rejected} |
```

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
Verdict: STORIES_READY (informational — plan validation gate follows)
Next: Plan Validation (challengers review the plan before Build)
      /build-implementation (per story, after plan approved)
      /estimation if sizing not yet done
      /story-writing if individual stories need refinement
Artifacts: [story list with ACs, points, parallel batches]
```
