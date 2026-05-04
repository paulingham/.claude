---
name: "verify"
description: "Use when user wants to Structured verification workflow: contract tests, smoke tests, mutation testing. Produces a tiered verification report with VERIFIED/UNVERIFIED verdict. Use after implementation to prove correctness beyond passing tests."
context: fork
agent: software-engineer
---

# Verification Workflow

## Current Context
- Branch: !`git branch --show-current`
- Changed files: !`git diff main...HEAD --name-only 2>/dev/null || echo 'N/A'`
- Diff stats: !`git diff main...HEAD --stat 2>/dev/null || echo 'N/A'`

## What This Skill Does

Proves a feature works correctly beyond just passing tests. Runs three verification tiers and produces a verdict.

## Verification Tiers

| Feature Type | Tier 1 (Contract) | Tier 2 (Smoke) | Tier 3 (Mutation) | Tier 4 (E2E) |
|-------------|-------------------|----------------|-------------------|--------------|
| Backend API | Hit real endpoint, verify response shape | curl + DB state check + log check | Mutate handler logic | N/A |
| Frontend | Props match API response shape | Playwright/browser screenshot | Mutate component logic | N/A |
| Mobile/WebView | Hook/service contract tests | Component render + prop verification | Mutation testing on lib/ business logic | Maestro (mobile) AND/OR Playwright/Cypress (web) — multi-target dispatch per `rules/_detail/e2e-protocol.md` |
| Web (browser) | API contract tests against real endpoint | Curl + DOM snapshot + log check | Mutate handler/component logic | Playwright/Cypress against deployed preview / docker-compose / cloud ephemeral env (conditional per `rules/_detail/e2e-protocol.md`) |
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

### 4. Run Tier 3: Mutation Testing (HARD GATE — >= 70% kill rate)

> **Tier 3 is a HARD GATE.** Kill rate >= 70% on changed lines is required for VERIFIED. Below threshold means UNVERIFIED — the slice returns to Build with the surviving-mutation list as targeted test gaps. Patch-critic also reads this report; a failing mutation gate is a deal-breaker for PATCH_APPROVED.

**Check tool availability first:**
- JavaScript/TypeScript: `which npx && npx stryker --version` (Stryker)
- Ruby: `bundle show mutant` (Mutant)
- Python: `which mutmut` (mutmut)

**If mutation testing tool is available:** run it on changed lines only (not the full file). Compute kill rate = killed / (killed + survived). Report the surviving-mutation list verbatim. Score < 70% → Tier 3 FAIL → UNVERIFIED.

**If mutation testing tool is NOT installed (manual fallback, still gated):**
1. For every conditional in the changed lines, mentally swap the condition (`>` → `<=`, `&&` → `||`, boundary off-by-one).
2. For each mutation, identify the test that catches it. If none, the mutation survives.
3. Compute kill rate = caught / total mutations checked. Score < 70% → Tier 3 FAIL → UNVERIFIED.
4. Report manual-fallback methodology, total mutations checked, and surviving-mutation list.

The manual fallback is approved as a gate-passing methodology — but the >= 70% threshold still applies. "Tooling unavailable" is not an exemption from the gate.

### 4.5. Run Tier 4: E2E Tests (Conditional, multi-target)

Tier 4 can run in parallel with Tier 3 (they are independent). Multi-target: mobile (Maestro) and web (Playwright / Cypress) dispatch independently per `rules/_detail/e2e-protocol.md`. Both can fire on the same change.

1. **Detect targets** via `hooks/_lib/e2e_target_resolver.py`:

   ```python
   from e2e_target_resolver import detect_targets, select_web_driver, \
       coerce_web_status_for_flake, compose_verdict
   firing = detect_targets(changed_files, project_root)
   # → {"mobile": "FIRED"|"N/A", "web": "FIRED"|"N/A"}
   ```

   - Mobile fires when: changed file matches a mobile glob AND `maestro/` directory exists.
   - Web fires when: changed file matches a web glob AND (`playwright.config.{ts,js}` OR `cypress.config.{ts,js}` is present).
   - Both matchers run independently — no short-circuit.

2. **For each fired target, execute its suite** per the protocol's per-target Execution section.

   - **Mobile** (Maestro): Check prerequisites (CLI, simulator, dev build, credentials). If unmet → mobile status = SKIP. Else select flows via the flow-to-file mapping (always include `app-launch.yaml`), execute, retry once on failure.
   - **Web** (Playwright/Cypress): Resolve driver via `select_web_driver(project_root)` — when both configs are present, prefer Playwright and emit the warning verbatim into the report. Check prerequisites (driver installed, real environment available). If unmet → web status = SKIP. Else execute the suite.

3. **Web flake handling (strict, no small-suite carve-out)**: capture intra-run flake_rate from the driver's retry counter, then coerce BEFORE composing.

   ```python
   coerced = coerce_web_status_for_flake(target_results, flake_rate)
   # web → FAIL when flake_rate > 0.05 (strict `>`).
   ```

   Document `flake_rate: <decimal>` in the verify report.

4. **Screenshots**: web E2E screenshots-on-assertion land at `pipeline-state/{task_id}/scratchpad/qa-engineer-verify-screenshots/` (mirrored as `SCREENSHOT_PATH_TEMPLATE` in the resolver — verbatim invariant).

5. **Composite verdict (COERCE FIRST, COMPOSE SECOND)**:

   ```python
   verdict = compose_verdict(coerced)
   ```

   - Any target = FAIL → UNVERIFIED
   - Any target = SKIP and no FAILs → VERIFIED_WITH_SKIP
   - All fired targets = PASS → VERIFIED
   - All N/A → VERIFIED

6. **First-fire release note**: on first web-target fire for a project (no prior `pipeline-state/{task_id}/scratchpad/qa-engineer-verify-screenshots/` history), emit one line in the verify report: "Web E2E gating now active because <reason>".

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

### Tier 4: E2E (multi-target — mobile + web)
- **Per-target status**:
  - Mobile (Maestro): PASS / FAIL / SKIP / N/A
  - Web (Playwright/Cypress): PASS / FAIL / SKIP / N/A
- **Composite (after coerce-then-compose)**: VERIFIED / VERIFIED_WITH_SKIP / UNVERIFIED
- **Mobile flows run**: [list of executed Maestro flow files]
- **Web driver**: Playwright | Cypress | (none — N/A)
- **Web flake_rate**: [decimal; FAIL if > 0.05 — strict `>`]
- **Driver-collision warning** (M4): [present iff both playwright + cypress configs detected]
- **Screenshots**: `pipeline-state/{task_id}/scratchpad/qa-engineer-verify-screenshots/` (web only)
- **Evidence**: [pass/fail per flow + per-spec, retry attempts, skip reason if applicable]

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
