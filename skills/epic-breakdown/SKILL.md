---
name: "Epic Breakdown"
description: "Decompose an epic into estimated stories with acceptance criteria. Orchestrates architect for design, estimation for sizing, and outputs structured stories. Use when breaking down epics or features into implementable stories."
---

# Epic Breakdown

## What This Skill Does

Decomposes an epic or feature request into thin vertical slices — each with acceptance criteria, story points, and implementation notes.

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
Apply elephant carpaccio — the thinnest possible vertical slices:
- Each story delivers end-to-end functionality (DB + API + UI + tests)
- Each story is independently deployable and testable
- Each story delivers observable user value
- If a story is 21+ points, it MUST be split further

### 4. Write Acceptance Criteria
For each story:
- **Given/When/Then** format for each AC
- At least one happy path and one error path
- Clear, testable, and unambiguous

### 5. Estimate Stories
Use Fibonacci scale (1, 2, 3, 5, 8, 13, 21):

| Points | Effort | Uncertainty |
|--------|--------|------------|
| **1** | Trivial | None |
| **2** | Simple | Minimal |
| **3** | Standard | Low |
| **5** | Moderate | Some |
| **8** | Complex | Moderate |
| **13** | Very complex | High |
| **21** | Must split | Very high |

Complexity factors (+1 level each):
- New technology or pattern
- Cross-service integration
- Database migration
- External API dependency
- Security-sensitive
- Performance-critical

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
- Never estimate to precision (use Fibonacci, not hours)
- Never pad estimates — surface uncertainty instead
- Never split into sub-tasks to reduce per-task size artificially
- Never create horizontal slices (all DB, then all API, then all UI)
