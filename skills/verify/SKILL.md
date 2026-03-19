---
name: "Verify"
description: "Structured verification workflow: contract tests, smoke tests, mutation testing. Produces a tiered verification report with VERIFIED/UNVERIFIED verdict. Use after implementation to prove correctness beyond passing tests."
context: fork
agent: software-engineer
---

# Verification Workflow

## What This Skill Does

Proves a feature works correctly beyond just passing tests. Runs three verification tiers and produces a verdict.

## Verification Tiers

| Feature Type | Tier 1 (Contract) | Tier 2 (Smoke) | Tier 3 (Mutation) | Tier 4 (E2E) |
|-------------|-------------------|----------------|-------------------|--------------|
| Backend API | Hit real endpoint, verify response shape | curl + DB state check + log check | Mutate handler logic | N/A |
| Frontend | Props match API response shape | Playwright/browser screenshot | Mutate component logic | N/A |
| Mobile/WebView | Hook/service contract tests | Component render + prop verification | Mutation testing on lib/ business logic | Maestro flows against running simulator (conditional per `rules/e2e-protocol.md`) |
| Database | Schema constraint tests | Migrate up+down, verify integrity | N/A | N/A |
| Infrastructure | Health endpoint responds | Readiness probe passes | N/A | N/A |

## Process

### Parallel Tier Execution

Where tiers are independent, run them in parallel:
- Tier 1 (Contract) and Tier 2 (Smoke) can often run simultaneously
- Tier 3 (Mutation) depends on test results from Tier 1/2, so runs after
- Tier 4 (E2E) is independent of Tier 3 and can run in parallel with it
- Use parallel Bash calls or parallel agent spawns for independent tiers

### 1. Identify Feature Type

Detect from changed files: API routes → Backend API, components → Frontend, hooks/lib → Mobile/WebView, migrations → Database, Dockerfile/CI → Infrastructure.

Read the project's tech stack pattern file if one exists at `~/.claude/skills/[stack]-patterns/SKILL.md` for tech-specific verification strategies.

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

### 4.5. Run Tier 4: E2E Tests (Conditional)

Tier 4 can run in parallel with Tier 3 (they are independent).

1. **Check trigger matrix**: Consult `rules/e2e-protocol.md` -- do any changed files appear in the "E2E Required" list?
   - If NO changed files match: Tier 4 status is N/A. Skip to step 5.
   - If YES: proceed to step 2.
2. **Check prerequisites**: Maestro CLI available, simulator booted, dev build installed, test credentials set.
   - If prerequisites not met: Tier 4 status is SKIP. Record the missing prerequisite. Proceed to step 5.
   - If prerequisites met: proceed to step 3.
3. **Select flows**: Use the flow-to-file mapping in `rules/e2e-protocol.md` to determine which flows to run. Always include `app-launch.yaml`.
4. **Execute**: Run selected flows. On failure, retry once per flow. If a flow fails twice, it is a genuine failure.

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

### Tier 4: E2E (Maestro)
- **Status**: PASS / FAIL / SKIP / N/A
- **Flows run**: [list of executed flow files]
- **Evidence**: [pass/fail per flow, retry attempts, skip reason if applicable]

### Verdict: VERIFIED / VERIFIED_WITH_SKIP / UNVERIFIED
[If VERIFIED_WITH_SKIP: Tier 4 was SKIP -- product-reviewer must acknowledge]
[If UNVERIFIED: which tier failed and why]
```

## Prerequisite

- Review phase complete: BOTH `/code-review` and `/security-review` returned APPROVE

## Phase Output

```
Verdict: VERIFIED / VERIFIED_WITH_SKIP / UNVERIFIED
Next: If VERIFIED → /qa-test-strategy
      If VERIFIED_WITH_SKIP → /qa-test-strategy (product-reviewer must acknowledge skip in Accept phase)
      If UNVERIFIED → return to Build phase to fix failing tiers, then re-review
Tier results: [PASS/FAIL/SKIP/N/A per tier with evidence]
Agent summaries: [verification summary]
```
