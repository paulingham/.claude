---
name: "Tech Spike"
description: "Time-boxed technical research workflow: question, explore, prototype, findings, recommendation. Use for evaluating technologies, investigating unknowns, or de-risking technical decisions."
context: fork
agent: architect
argument-hint: "Technical question to investigate"
---

# Tech Spike

## What This Skill Does

Structured technical research to answer a specific question within a time-boxed scope. Produces actionable findings and a clear recommendation.

## Process

### 1. Define the Question
- What specific question are we trying to answer?
- What decision depends on this answer?
- What are the success criteria for the spike?
- Time box: how long should this take? (default: 2-4 hours)

### 2. Explore Options
- Identify 2-4 candidate approaches or technologies
- For each option, research:
  - How it works (architecture, API surface)
  - Maturity and community support
  - Integration effort with our stack
  - Known limitations and gotchas
  - Licensing and cost implications

### 3. Prototype
Build a minimal proof-of-concept for the top 1-2 options:
- Smallest possible working example
- Exercise the specific capability we need
- Measure what matters (performance, DX, bundle size, etc.)
- Document any surprises or blockers

### 4. Document Findings

```markdown
## Tech Spike: [Question]

### Context
[Why we're investigating this]

### Options Evaluated

#### Option A: [Name]
- **Pros**: [list]
- **Cons**: [list]
- **Prototype result**: [what we learned]
- **Integration effort**: [estimate]

#### Option B: [Name]
- **Pros**: [list]
- **Cons**: [list]
- **Prototype result**: [what we learned]
- **Integration effort**: [estimate]

### Recommendation
**Choose [Option X]** because [rationale tied to success criteria].

### Risks
- [Risk 1 and mitigation]
- [Risk 2 and mitigation]

### Next Steps
- [ ] [Action item 1]
- [ ] [Action item 2]
```

### 5. Recommend
- Clear recommendation tied to the original question
- Rationale mapped to success criteria
- Risks and mitigations identified
- Concrete next steps

## Anti-Patterns
- Don't go beyond the time box — the point is to reduce uncertainty, not eliminate it
- Don't build a real feature during a spike — prototypes are throwaway
- Don't evaluate more than 4 options — narrow first, then spike
- Don't skip the prototype — reading docs alone isn't sufficient

## Phase Output

```
Verdict: SPIKE_COMPLETE (informational — no gate)
Next: Depends on recommendation. Typically /build-implementation or /epic-breakdown.
Artifacts: [findings doc with recommendation, prototype code (throwaway)]
```
