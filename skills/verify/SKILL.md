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

| Feature Type | Tier 1 (Contract) | Tier 2 (Smoke) | Tier 3 (Rule-Based Mutation) | Tier 3.5 (LLM-Mutant) | Tier 4 (E2E) |
|-------------|-------------------|----------------|------------------------------|------------------------|--------------|
| Backend API | Hit real endpoint, verify response shape | curl + DB state check + log check | Mutate handler logic | ≥60% kill rate | N/A |
| Frontend | Props match API response shape | Playwright/browser screenshot | Mutate component logic | ≥60% kill rate | N/A |
| Mobile/WebView | Hook/service contract tests | Component render + prop verification | Mutation testing on lib/ business logic | ≥60% kill rate | Maestro (mobile) AND/OR Playwright/Cypress (web) — multi-target dispatch per `protocols/e2e-protocol.md` |
| Web (browser) | API contract tests against real endpoint | Curl + DOM snapshot + log check | Mutate handler/component logic | ≥60% kill rate | Playwright/Cypress against deployed preview / docker-compose / cloud ephemeral env (conditional per `protocols/e2e-protocol.md`) |
| Database | Schema constraint tests | Migrate up+down, verify integrity | N/A | N/A | N/A |
| Infrastructure | Health endpoint responds | Readiness probe passes | N/A | N/A | N/A |

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

### 4.25. Run Tier 3.5: LLM-Mutant Pass (HARD GATE — ≥60% kill rate)

> **Tier 3.5 is ADDITIVE to Tier 3, NOT a replacement.** Tier 3 retains its ≥70% rule-based mutation gate. Tier 3.5 layers a Claude-driven semantic-mutant pass on top: rule-based catches operator-shape bugs (5x cheaper); LLM-based catches intent-shape bugs (Wang et al.'s 46.3 pp lift on fault detection). Both gates must pass for VERIFIED. Iron Law 1's 70% mutation requirement on changed lines refers to Tier 3 — Tier 3.5 ships its own per-tier gate at 60%.

**Prerequisite**: Tier 3 has produced a mutation report. Read its surviving-mutation list to dedup — Tier 3.5 does not re-propose mutations Tier 3 already covered.

**Operator categories (5 fixed, no others):**
- `off-by-one` — boundary mutations (`<` ↔ `<=`, `i + 1` ↔ `i`, range/slice endpoints).
- `wrong-comparator` — comparator swaps (`==` ↔ `!=`, `>` ↔ `<`, `&&` ↔ `||`).
- `swapped-args` — same-typed arguments transposed at call sites.
- `null-vs-empty` — `null`/`undefined`/`None` ↔ empty collection (`[]`, `""`, `{}`).
- `async-without-await` — dropped `await` on a Promise/Future, dropped `.catch`/error path on async work.

**Mutant generation (ONE Claude call per slice — NO retry):**

1. Issue ONE call to Claude with the changed-line diff, the 5 operator categories above, and the Tier 3 surviving-mutation list (for dedup). Request 5–10 mutants — fewer is acceptable, more must be truncated to 10.
2. Each mutant in the response carries the schema:
   ```
   {
     file:        <relative path>,
     line_range:  <"start-end" or "line">,
     original:    <verbatim source snippet>,
     mutated:     <verbatim mutated snippet>,
     category:    <one of the 5 above>,
     rationale:   <why this is a plausible bug>,
     equivalent:  <yes | no | unsure>
   }
   ```
3. **Equivalence filter**: drop any mutant with `equivalent: yes` from the kill-rate denominator. `unsure` defaults to inclusion (conservative — counts against kill rate unless killed). `equivalent: yes` requires a one-line rationale; code-reviewer + patch-critic spot-check.
4. **Cost guardrail**: ONE call per slice, max 10 mutants per response. NO retry. If the call times out, returns malformed output (parse failure), or returns zero non-equivalent mutants → Tier 3.5 = **SKIP** with documented reason → composite verdict becomes **VERIFIED_WITH_SKIP**. Product-reviewer must acknowledge the skip in the Accept phase.

**Per-mutant apply-test-revert loop:**

1. Apply the mutant in a scratch worktree (`git stash` snapshot or temporary branch — NEVER in-place edits to the active worktree).
2. Run the test suite.
3. **Killed**: a test fails on the mutated code (the mutation was caught).
4. **Survived**: the suite stays green on the mutated code (the mutation slipped past tests).
5. **Timed-out**: treat as **killed** (Stryker semantics — runaway tests indicate the mutation broke a tight loop).
6. Revert the mutant before applying the next one.

**Per-tier gate:**
```
kill_rate = killed / (killed + survived)
```
where the denominator excludes `equivalent: yes` mutants. **kill_rate ≥ 0.60 required.** Below threshold → Tier 3.5 = **FAIL** → composite verdict becomes **UNVERIFIED**, slice returns to Build with the surviving-mutant list as targeted test gaps.

**Audit-trail invariant**: Tier 3.5 results **APPEND to the existing mutation report** produced by Tier 3 — they do NOT generate a new report file. The audit-trail count locked by `protocols/atdd-procedure.md` (3 artifacts: batched RED, GREEN, mutation-report) is preserved.

**Cross-reference**: `orchestrator/parallel-dispatch-details.md` § Multi-Persona Patch Critic Dispatch / Execution Evidence reuses the same call-shape pattern documented in this section (ONE call, NO retry, max-N items per response, JSON schema, parse-failure → silent skip). The procedure body above is the canonical wording source; the patch-critic execution-evidence layer inlines + adapts it. Tier 3.5's verify-time semantics are unchanged by that reuse.

**Citations:**
- arXiv 2406.09843 (Wang et al., 2024) — LLM-generated mutants achieve 87.98% fault detection vs 41.64% rule-based (46.3 pp lift) on a comprehensive benchmark; motivates Tier 3.5 as additive to Tier 3.
- arXiv 2404.09952 (LLMorpheus, 2024) — measured ~18.2% structurally equivalent / near-equivalent mutant rate (8.5% equivalent + 9.7% near-equivalent), capping achievable kill rate at ~80–82% for LLM-mutant suites; motivates the 60% per-tier gate (headroom for tooling variance below the structural ceiling).

### 4.5. Run Tier 4: E2E Tests (Conditional, multi-target)

Tier 4 can run in parallel with Tier 3 (they are independent). Multi-target: mobile (Maestro) and web (Playwright / Cypress) dispatch independently per `protocols/e2e-protocol.md`. Both can fire on the same change.

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

### 6. Write Verification Evidence State File

The verifier MUST write `pipeline-state/{task-id}/verification-evidence.json` at the end of every tier-completion using `os.replace` (atomic rename — write to `verification-evidence.json.tmp` first, then `os.replace` to the canonical path). Resolve the write target via `_psp_verification_evidence_path "${CLAUDE_PIPELINE_TASK_ID}" "${CLAUDE_WORKSTREAM:-}"` relative to `$CLAUDE_REPO_ROOT` (NEVER relative to cwd — `/verify` runs inside the build worktree but the state-file path must resolve against the repo root). Schema: `{schema_version: 1, task_id, git_head, generated_at, verdict, tier_results, sandbox_run}` — see `protocols/_proposals/2026-05-14-iron-law-2-freshness-hook.md` for the field definitions. The Path-B advisory hook `hooks/verification-freshness-guard.sh` reads this file on every gated spawn (patch-critic, product-reviewer, pr-creation) and compares the recorded `git_head` to the current worktree HEAD.

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

### Tier 3.5: LLM-Mutant Pass
- **Status**: PASS / FAIL / SKIP / N/A
- **Score**: [X/Y mutants killed (excluding equivalent)]
- **Equivalent excluded**: [N]
- **Uncaught**: [list of surviving non-equivalent mutants with category + rationale]
- **Skip reason** (if SKIP): [reason — call timeout, parse failure, zero non-equivalent mutants returned]

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

**Verdict semantics**:
- **VERIFIED** — Tier 3 (≥70% rule-based) AND Tier 3.5 (≥60% LLM-mutant) both PASS (or both N/A per the tier matrix). Tier 4 fired and PASSED (or all N/A).
- **VERIFIED_WITH_SKIP** — at least one tier was SKIP (Tier 3.5 SKIP on Claude-call failure; Tier 4 SKIP per E2E protocol prerequisites unmet) AND no tier FAILED. Product-reviewer must acknowledge the skip in the Accept phase.
- **UNVERIFIED** — any tier FAILED. Slice returns to Build with the failing tier's evidence (surviving-mutant list, failing E2E flows) as targeted gaps.

[If VERIFIED_WITH_SKIP: name which tier was SKIP and why -- product-reviewer must acknowledge]
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
Tier results: Tier 1: [PASS/FAIL] | Tier 2: [PASS/FAIL] | Tier 3: [PASS/FAIL/N/A] | Tier 3.5: [PASS/FAIL/SKIP/N/A] | Tier 4: [PASS/FAIL/SKIP/N/A]
Agent summaries: [verification summary]
```
