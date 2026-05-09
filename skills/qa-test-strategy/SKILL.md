---
name: "qa-test-strategy"
description: "Use when user wants to Test phase skill: spawn qa-engineer to map acceptance criteria to tests, identify coverage gaps, and write integration/E2E tests. Uses worktree for test authoring."
context: fork
agent: qa-engineer
---

# QA Test Strategy

## What This Skill Does

Automates the Test phase. Spawns a qa-engineer to validate test coverage against acceptance criteria and write missing tests.

## When to Invoke

- After Verify phase passes (verification report says VERIFIED)
- Before Accept phase

## Process

### 1. Gather Context

Collect acceptance criteria, changed files, and existing test files.

### 2. Spawn QA Engineer

```
Agent({
  subagent_type: "qa-engineer",
  isolation: "worktree",
  prompt: "Analyze test coverage for this feature:
    Acceptance Criteria: [list ACs]
    Changed files: [list files]

    1. Map each AC to existing test(s) that verify it
    2. Identify gaps: ACs without tests, missing error paths, untested edge cases
    3. Write integration tests for gaps (including frozen PBT counterexamples promoted to unit tests by `/property-based-test` at Build Step 1d)
    4. Write E2E test flows for critical user paths
    5. Verify 80% coverage on critical paths

    6. Analyze maestro/ E2E flows:
       - Map user journeys to existing Maestro flows
       - Verify flows exist for changed behavior (see rules/e2e-protocol.md trigger matrix)
       - If new domains or auth paths were added, verify corresponding flows exist
       - If existing flows no longer reflect current behavior, flag as GAP
       - Write new Maestro flows if gaps are found (follow patterns in ~/.claude/skills/react-native-patterns/SKILL.md)

    Output a test coverage report mapping each AC to its test(s)."
})
```

Uses `isolation: "worktree"` — qa-engineer writes test files.

### Property-Based Coverage Verification (Final-Gate role)

PBT authoring is performed earlier in the pipeline by `/property-based-test` at Build Step 1d (see `skills/property-based-test/SKILL.md`). At Final Gate, qa-engineer's responsibility is **verification only**:

- Confirm ≥1 property exists per public function on changed lines, OR a documented justification why a property is impossible (per the QA Checklist below).
- Confirm any frozen counterexamples joined the deterministic unit-test tier with harness-native syntax (`@example` / seeded `fc.assert`).
- Report the matrix in the `### Property-Based Coverage Report` section of the Test Coverage Report Format.

If the matrix is incomplete, return GAPS_FOUND and dispatch fix-engineer (per `rules/_detail/pipeline-protocol.md` § In-Cycle Fix Rule). qa-engineer does NOT author PBTs at this gate — re-running `/property-based-test` is the in-cycle fix path.

### 3. Process Report

- **All ACs covered, no gaps**: Advance to Accept phase. Record QA summary for PR narrative.
- **Gaps identified**: QA engineer writes missing tests in worktree. Re-verify coverage.

### QA Checklist

- [ ] Flag tests that only assert type or callability (`typeof X === 'function'`) -- these are coverage padding, not behavior tests
- [ ] Every test asserts observable behavior (return values, state changes, side effects), not implementation details
- [ ] Coverage numbers reflect real behavior verification, not padding
- [ ] **PBT run produced ≥ 1 property per public function on changed lines, OR a documented justification why a property is impossible** (`agents/qa-engineer.md` mirrors this item)
- [ ] Frozen counterexamples from PBT runs are captured as deterministic unit tests (`@example` / seeded `fc.assert`)
- [ ] Maestro E2E flows exist for changed behavior that touches trigger files (see `rules/e2e-protocol.md`)
- [ ] New domains, auth providers, or URL patterns have corresponding E2E flows
- [ ] Existing Maestro flows still reflect current app behavior (no stale selectors or outdated URLs)

## Test Coverage Report Format

```markdown
## Test Coverage Report

### AC Coverage Matrix
| AC | Test File | Test Name | Status |
|----|-----------|-----------|--------|
| AC1: Given X when Y then Z | __tests__/feature.test.ts | "should Z when Y" | COVERED |
| AC2: Given A when B then C | — | — | GAP |

### Gap Analysis
- **Missing**: [list of untested ACs or paths]
- **Weak**: [list of ACs with insufficient assertions]

### Property-Based Coverage Report
| Function | Path | Properties | Outcome | Counterexamples Frozen |
|----------|------|-----------|---------|------------------------|
| `parse_csv` | `lib/parser.py` | inverse(decode∘encode), idempotence(strip-bom) | passed_within_budget | — |
| `normalize_url` | `lib/url.ts` | idempotence | counterexample | `'http://X//y' → seed 0xab12` |
| `dispatchSdkCall` | `lib/sdk.ts` | — | justified-impossible: pure SDK pass-through | — |

- **Functions covered**: N
- **Properties run**: N
- **Counterexamples frozen as unit tests**: N
- **Functions with documented justification**: N

### Integration Tests Written
- [list of new test files/cases]

### E2E Flows (Jest)
- [list of E2E scenarios covered]

### E2E Flow Coverage (Maestro)
| User Journey | Maestro Flow | Status |
|-------------|-------------|--------|
| App launch and load | `app-launch.yaml` | COVERED / GAP |
| Adviser login | `adviser-login-flow.yaml` | COVERED / GAP |
| Client login | `client-login-flow.yaml` | COVERED / GAP |
| Offline handling | `offline-banner.yaml` | COVERED / GAP / N/A |
- **New flows written**: [list of new Maestro YAML files created]
- **Stale flows updated**: [list of updated Maestro YAML files]

### Verdict: COVERED / GAPS_FOUND
```

## Prerequisite

- Verify phase complete: `/verify` returned VERIFIED

## Phase Output

```
Verdict: COVERED / GAPS_FOUND
Next: If COVERED → /product-acceptance
      If GAPS_FOUND → QA writes missing tests in worktree, re-verify coverage, then re-run this skill
Coverage: [percentage on critical paths]
Agent summaries: [qa-engineer's 2-3 sentence summary]
```
