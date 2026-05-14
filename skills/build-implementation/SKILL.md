---
name: "build-implementation"
description: "Use when user wants to Structured build phase: read per-AC failing-test stubs from the architect, implement via the ATDD protocol (batched RED, implement cleanly, mutation gate), enforce cohesion-based shape rules. Use at the start of any Build phase."
context: fork
agent: software-engineer
argument-hint: "Acceptance criteria or story to implement"
---

# Build Implementation

## What This Skill Does

Prescribes the exact procedure for the Build phase of the delivery pipeline. Engineers consume the architect's per-AC failing-test stub list, implement each slice via the ATDD cycle (two test invocations per slice plus a mutation gate), and enforce cohesion-based shape rules continuously.

## Dispatch Mode

This skill is dispatched via the Agent tool with `isolation: "worktree"`. The orchestrator NEVER invokes this skill via the Skill tool directly. The agent reads this file and executes it in an isolated worktree.

## Procedure

### Step 1: Read AC Test Stubs from the Plan

Before writing any code:
1. Open `pipeline-state/{task-id}/plan.md` and locate the **Failing Test Stubs (per AC)** section the architect produced.
2. For each AC in this slice, the stub list names: test file path, test name, assertion intent.
3. **If any AC has no stub, halt immediately** — surface the gap to the architect and request a stub. Implementation cannot begin without a complete stub list.
4. The stub list IS your implementation plan. Three test invocations per slice — not three per AC, three per slice. See `protocols/atdd-procedure.md` for the full cycle.

### Step 1b: Install Required Dependencies

If the implementation requires new packages not yet in `package.json`:
1. Install the package: `npm install <package>` (or equivalent)
2. Verify the installation: `npm ls <package>` (or equivalent)
3. Commit `package.json` and lock file separately: "chore: add <package> for <reason>"
4. Proceed with the batched-RED step — the first failing batch validates the dependency works.

If the orchestrator's prompt specifies dependencies, install them here. If you discover a needed dependency during implementation, install it at that point.

### Step 1c: Write Contract Assertions (Tier 0 — Spec-as-Contract)

Inserted between "Read AC Test Stubs" and "Batched RED". Required for every slice that touches a contract listed in `pipeline-state/{task-id}/intake.md` § Contracts Touched. If `(none)` was recorded at intake, skip this step (no public surface changed).

For each contract in the list:

1. Author a **runtime assertion** at the module port that encodes the contract:
   - **Public function signatures** → input/output type guards (e.g., `assertSchema(Input, x)` at the start, `assertSchema(Output, y)` before returning).
   - **JSON schemas** → schema validators (`zod`, `pydantic`, `ajv`, `cerberus`) at the boundary; reject malformed input with structured errors.
   - **OpenAPI paths** → request/response validation middleware (`openapi-validator`, `dredd`, `Pact`) wired into the route handler.
   - **DB schemas** → constraints declared in the migration (NOT NULL, FOREIGN KEY, CHECK) AND mirrored in the ORM/data-access layer for fail-fast at write time.
   - **Invariants** → a runtime check at the place the invariant must hold (`invariant(predicate, message)`), authored as a re-usable helper not a one-off `if`/`throw`.

2. Author a **failing contract test** for each assertion in a `*.contract.spec.{ts,js,py,rb,go}` file (Tier 0 in `protocols/engineering-invariants.md` § Proof of Correctness):
   - The test feeds a *deliberately invalid* input and asserts the contract rejects it with the structured error.
   - The test feeds a *valid* input and asserts the contract accepts it and the downstream behavior runs.

3. Run the suite ONCE before any implementation. Capture the **Tier-0 RED output** — the contract assertions must fail because the production code that wires them is not yet written. This is the audit artifact for Tier 0.

The Tier-0 RED output is a separate capture from the Step-2 BATCHED RED output. Both are required as audit artifacts for the slice (per `protocols/atdd-procedure.md` § Audit Trail).

### Step 1d: Author Property-Based Tests (Tier 1.5)

Inserted between Tier 0 contract assertions (Step 1c) and Step 2 batched RED. Authors Tier 1.5 property-based tests for every public function on changed lines with a typed signature. Auto-invoked on every Build run unless `CLAUDE_PBT=0`. The output files match the existing `tests/**/*.property.{spec,test}.*` glob byte-for-byte so Step 2b cap-detection (5→3) fires automatically against the just-authored properties.

Procedure:

1. Invoke `/property-based-test` (see `skills/property-based-test/SKILL.md`). The skill spawns `pbt-engineer` in your worktree (worktree-reuse, mirrors `fix-engineer`).
2. The engineer identifies candidate functions from `git diff --name-only` (public, typed signature, on changed lines), picks the harness from the language → framework table, generates ≥1 property per candidate from one of `{idempotence, inverse, oracle, metamorphic}`, time-boxes 60s/function, and freezes any counterexamples inline using harness-native syntax (`@example`, seeded `fc.assert`, frozen `?FORALL`).
3. Read the verdict and act accordingly:
   - **`PBT_AUTHORED`** — ≥1 property authored. Proceed to Step 2.
   - **`PBT_SKIPPED`** with reason `env-hatch` (operator set `CLAUDE_PBT=0`), `no-candidates` (no public-typed-changed-line functions), or `no-framework-for-language` (language has no shipped harness or harness not installed). All three skip reasons are benign — proceed to Step 2.
   - **`PBT_BLOCKED`** with reason `harness-crash` or `unrecoverable-error` — HALT Build. Surface the verdict payload (function name, 5-line error excerpt, `CLAUDE_PBT=0` recovery action, retry-twice-then-escalate exemption per `protocols/operational-protocol.md`) to the orchestrator.

**Escape hatch.** Set `CLAUDE_PBT=0` in the environment to disable Step 1d — this skips PBT authoring entirely. The hatch exists for the soak window (default-on) so cycle-time impact can be measured before flipping to mandatory; it is the one-line revert path if pbt-engineer introduces unexpected runtime cost.

### Step 2: Implement Slice via ATDD (Two test invocations per slice)

Follow the ATDD Protocol in `protocols/atdd-procedure.md`:

1. **BATCHED RED**: Write every AC test as one batch (the architect's stubs verbatim). Run the suite ONCE. Capture the RED output. Verify each test fails for the right reason — the named behavior is absent. The Tier-0 contract tests authored in Step 1c are also part of this batch (they are still RED unless the contract assertion was implementable in isolation in Step 1c).
2. **IMPLEMENT CLEANLY**: Write production code that is correct AND well-shaped on the first pass. Cohesion rules (one-thing-per-function, CC ≤ 5, nesting ≤ 2, DRY on 2nd occurrence) apply *as you write*, not in a separate cleanup pass. Choose intent-revealing names from the start; extract duplication on the 2nd occurrence as it appears. Run the suite ONCE when done. Capture the GREEN output. After the suite run inside IMPLEMENT CLEANLY, on RED follow Step 4a–4c.
3. **MUTATION GATE**: Run mutation testing on changed lines (Stryker / Mutant / mutmut, or the manual fallback in `skills/verify/SKILL.md`). Score >= 70% required against the **union suite** (architect stubs + adversarials from Step 2b). If <70%, add tests targeting the surviving mutations and return to step 2 — the slice is NOT complete.
4. **COMMIT** with the three audit artifacts: batched RED output, GREEN output, mutation report.

**Exception cycles** — bug fixes, complex algorithmic logic, and security-sensitive code retain per-behaviour RED-GREEN. See `protocols/atdd-procedure.md` § When per-behaviour TDD Still Applies (Exceptions). For those cases follow `skills/bug-fix/SKILL.md` instead of the batched cycle.

### Step 2b: Adversarial Test Categories (greenfield ACs default-on, refactor slices env-gated)

After Step 2's IMPLEMENT step lands GREEN and BEFORE the MUTATION GATE finalises, generate adversarial tests that probe edge cases the architect's stubs do not cover. Adversarials are AC-adjacent edge probes — they belong AFTER architect stubs are GREEN, not before. Inspired by AlphaCodium (arXiv 2401.08500) test-iteration loop.

**Bug-fix slices SKIP this step entirely.** For bug-fix work, the repro test IS the contract — adversarial probing belongs in greenfield AC implementation, not regression closure. See `skills/bug-fix/SKILL.md` for the per-behaviour cycle that applies instead.

**Refactor slices.** For refactor slices, Step 2b is opt-in (default OFF — soak window). When enabled, generate adversarials with **cap=3** (not the greenfield cap=5) — refactors change implementation, not contract, so a tighter cap bounds cycle time while still surfacing implementation regressions. The 5-category walk and discipline rules below apply unchanged; only the cap differs. Enable per pipeline by exporting `CLAUDE_ADVERSARIAL_TESTS_REFACTOR=1` in the build agent's environment. The flag is additive over the master kill-switch — `CLAUDE_ADVERSARIAL_TESTS=0` overrides any value of `CLAUDE_ADVERSARIAL_TESTS_REFACTOR` and skips Step 2b regardless.

**Precedence truth table.** The two env vars and the slice's task class compose as follows. The master kill-switch wins; the refactor opt-in is additive only when the master is unset/`1`; bug-fix always skips:

| `CLAUDE_ADVERSARIAL_TESTS` | `CLAUDE_ADVERSARIAL_TESTS_REFACTOR` | task class | Step 2b behavior |
|---|---|---|---|
| `CLAUDE_ADVERSARIAL_TESTS=0` | any | any | SKIPPED (master kill-switch wins) |
| unset / `1` | unset / `0` | greenfield | RUNS, cap=5 |
| unset / `1` | `CLAUDE_ADVERSARIAL_TESTS_REFACTOR=1` | refactor | RUNS, cap=3 |
| unset / `1` | unset / `0` | refactor | SKIPPED (soak default-off) |
| any | any | bug-fix | SKIPPED (bug-fix iron law) |

**Escape hatch.** Set `CLAUDE_ADVERSARIAL_TESTS=0` in the environment to disable Step 2b — this skips Step 2b entirely on every task class (greenfield, refactor, bug-fix). The hatch exists for the soak window (default-on for greenfield) so cycle-time impact can be measured before flipping to mandatory; it is the one-line revert path if adversarial generation introduces unexpected runtime cost.

**Procedure.** Generate **3-5 adversarial tests** (HARD CAP at 5 — bound the cycle time). Walk the categories below in order, stop at 5 once the cap is reached even if later categories were not exercised. Each adversarial follows **RED-then-GREEN** — write the test, run the suite, confirm it fails for the right reason, then implement (or correct production code) until it passes. This is the same audit-trail contract as the architect's stubs; a captured RED is the audit artifact.

Walk these 5 categories IN ORDER:

1. **Boundary values** — off-by-one (`n-1`, `n`, `n+1`), empty collection, single-element, max int / max string length where the language allows.
2. **Null / empty / undefined** — every input where the type allows. Skip if the type forbids (e.g., a non-nullable `int` parameter in Kotlin needs no null adversarial).
3. **Malformed input (parser-level only)** — malformed JSON, malformed dates, encoding edge cases (BOM, mixed UTF-16, lone surrogates). Only when changed code parses external input — skip for code that receives already-parsed structures.
4. **Error-path coverage** — for every catch / rescue / except block on changed lines, write one test that triggers it and asserts the block's claimed behavior. The catch block exists to do something — assert it does that thing.
5. **Concurrency races** — ONLY when changed code touches shared mutable state (module-level mutable, singleton instance state, file lock, DB row write without transaction). Skip for pure / per-request / per-instance code.

**Discipline rules.**

- **passes immediately = delete.** An adversarial that goes GREEN on its first run without any production-code change has no diagnostic value — the existing tests already cover the case, or the named edge does not actually exist on the changed lines. Delete it; do not keep it as a vanity test.
- **HALT if adversarial reveals contract gap.** If an adversarial surfaces a behavior the AC does not specify (e.g., what should happen on negative input when the AC is silent), HALT and surface to the architect. Do not invent the contract — the architect owns the spec, the engineer owns the implementation.

**PBT overlap.** When a function has **Tier 1.5** property-based tests covering it (per `protocols/engineering-invariants.md` § Proof of Correctness), **cap reduces from 5 to 3** for that function. PBTs already exercise boundary values and null/empty cases at the property level; adversarials should focus on **error-path + concurrency** which PBTs cover poorly. Detection is mechanical — file glob `tests/**/*.property.{spec,test}.*` next to the changed file → cap=3. Step 1d now produces those PBTs in-pipeline (auto-invoked unless `CLAUDE_PBT=0`), so the cap-reduction fires by default on every PBT-eligible function.

After adversarials are GREEN, return to Step 2's MUTATION GATE on the **union suite** (architect stubs + adversarials).

### Step 3: Shape Check After Every File

After completing or modifying ANY file, verify the cohesion-based shape rules in `protocols/engineering-invariants.md` § Code Shape:

- One thing per function (name has no conjunction)
- CC ≤ 5, nesting ≤ 2
- DRY on 2nd occurrence
- Single public entry point per class

Soft warnings (function > 30 lines, file > 150 lines) are smell signals — refactor when extraction has a real seam, leave alone when the unit is genuinely cohesive. The hook's 300-line safety net catches runaway output only.

If any hard rule is violated, refactor BEFORE moving to the next test case.

### Step 3b: Optional Tool Synthesis Escalation

If the standard toolset (Read, Grep, Glob, Bash one-liners, project-shipped scripts) is insufficient and a one-shot scratch tool would unblock progress, invoke `/tool-synthesis`. Triggers (any one):

- The same lookup/transformation has been performed manually **3+ times** in this task
- No extant tool covers the operation cleanly (no `rg` pattern, no `ast-grep` rule, no project script)
- A repo-specific concern (custom DSL, generated file, codebase convention) makes off-the-shelf tools wrong

The synthesised tool lives in `${WORKTREE}/.claude-scratch-tools/`, is invoked via Bash, and is cleaned up before BUILD_COMPLETE. It NEVER reaches `main`. See `skills/tool-synthesis/SKILL.md` for the full procedure.

If a built-in tool covers it, USE IT — do not synthesise.

### Step 4: Self-Review Checklist Before Done

Before declaring the build complete:
- [ ] Every AC has at least one passing test
- [ ] Every function does one thing (name has no conjunction)
- [ ] Cyclomatic complexity ≤ 5; nesting ≤ 2
- [ ] No DRY violations (no logic duplicated 2+ times)
- [ ] Functions > 30 lines or files > 150 lines: justified or refactored (advisory smell signals, not hard caps)
- [ ] All tests pass
- [ ] ATDD audit trail visible (batched RED + GREEN + mutation report ≥ 70%)
- [ ] Step 2b ran with the correct cap for the slice's task class (greenfield: default-on, cap=5; refactor: opt-in via `CLAUDE_ADVERSARIAL_TESTS_REFACTOR=1`, cap=3), OR was skipped per `CLAUDE_ADVERSARIAL_TESTS=0` (master kill-switch), OR is N/A for a bug-fix slice
- [ ] Step 1d ran (PBT_AUTHORED or PBT_SKIPPED), OR was skipped per `CLAUDE_PBT=0`
- [ ] If changes touch URL/auth/nav/WebView files: note that E2E will be required in Verify phase (see `protocols/e2e-protocol.md` trigger matrix)
- [ ] If `/tool-synthesis` was invoked: `register.sh --cleanup ${WORKTREE}` ran AND `git status` shows no `.claude-scratch-tools/` entries

## Worktree Isolation

All engineers spawned during Build MUST use `isolation: "worktree"`:

```
Agent({
  subagent_type: "frontend-engineer",
  isolation: "worktree",
  prompt: "Implement [AC] following incremental TDD...
    Also read the project's tech stack pattern file if one exists
    at ~/.claude/skills/[stack]-patterns/SKILL.md for tech-specific guidance."
})
```

**Parallel worktrees for independent slices:**
- If multiple ACs are independent (no shared files), spawn separate engineers in parallel worktrees
- Each worktree gets its own isolated copy of the repo
- Use a single message with multiple Agent calls to maximize parallelism
- If ACs share files, implement sequentially — merge first worktree before starting next

## Anti-Patterns

- Skipping the mutation gate → BLOCKED (a green suite is not the deliverable; the mutation report is)
- Implementing before the batched-RED output is captured → BLOCKED (RED is the audit artifact)
- Starting work when one or more ACs has no architect-produced test stub → BLOCKED (halt, surface to architect)
- Deferring shape violations to "clean up later" → BLOCKED
- Skipping the self-review checklist → BLOCKED

## Prerequisite

- Plan phase complete: story/AC defined (from `/epic-breakdown` or `/story-writing`)
- OR: refactoring target identified (use `/refactor` instead)
- OR: bug reproduction steps known (use `/bug-fix` instead)

## Self-Review Gate (Mandatory Before Completion)

Before producing the Phase Output, the build agent MUST self-review:

1. **Type safety**: Run `tsc --noEmit` — zero errors
2. **Tests green**: Run full test suite — all passing
3. **Re-read all changed files** and check:
   - Function names reveal intent
   - No duplication across files (extract on 2nd occurrence)
   - Single responsibility per function/file
   - No unused imports, dead code, or commented-out blocks
   - Guard clauses over nested conditionals
4. **Fix everything found** — do not leave mechanical issues for the reviewer
5. **Shape compliance**: Hooks enforce this automatically. If a hook blocks your write, fix immediately.

The goal: the code-reviewer should find ZERO mechanical issues. Only design-level feedback should survive to review.

## Built-In Verification (Budget 5-8)

For small tasks (Complexity Budget 5-8), the build agent performs its own verification before completing:

1. **Contract tests**: Verify all new functions have tests that assert their contracts (inputs → outputs)
2. **Mutation spot-check**: For each function with conditional logic, mentally check: "If I swapped the branches, would a test catch it?" If not, add the test.
3. **Integration check**: If the change wires into an existing component, verify the integration test covers it.

This reduces the need for separate Verify and QA phases on small tasks. For Budget 9+ tasks, separate Verify and QA phases still apply.

### Step 4a: On-RED Branch

After running the suite at the end of Step 2 step (2) IMPLEMENT CLEANLY — or any subsequent same-suite invocation in this slice — if GREEN proceed to Step 5. If RED, enter the iterative-refinement loop (Step 4b). The loop is the Build phase's in-cycle fix mechanism (Iron Law 6); `/bug-fix` is invoked only on exhaustion (Step 4c). Mutation-gate failure at Step 2 step (3) is NOT the trigger for this loop — it has its own remediation (add tests, return to Step 2).

### Step 4b: Iterative Refinement on RED (ReVeal, arXiv 2506.11442)

1. Append a finding to `pipeline-state/{task-id}/scratchpad/{role}-build.md` with `category: test-failure-feedback`. Body:
   - (a) failing test names,
   - (b) first 20 lines of failure output,
   - (c) one-sentence root-cause hypothesis,
   - (d) attempted-edit summary (file:line ranges).
   WRITE THIS ENTRY BEFORE EDITING — count of entries IS the counter; writing after the edit double-counts. Agent crash mid-loop counts as a failed iteration (no resume semantics; the counter is durable on disk but the corresponding edit may be absent).
2. Read the scratchpad — count prior `test-failure-feedback` findings. This count is the `iteration_index` (0-based: first entry = index 0).
3. If `iteration_index + 1` reaches `MAX_ITER` (the cap from Step 4c env-var), exit to Step 4c.
4. Author a refined edit informed by the failure output AND every prior `test-failure-feedback` entry. Do NOT re-propose a hypothesis already in the log (the entries are the failed-hypothesis log).
5. Re-run the suite ONCE — the SAME suite invocation that produced the prior RED (project-default test command unless the slice scoped narrower; do not silently re-scope). GREEN → Step 5. RED → return to step 1.

Each iteration appends exactly one `test-failure-feedback` finding; the count IS the counter. Inspired by ReVeal's iterative test-feedback refinement (arXiv 2506.11442).

### Step 4c: Exhaustion — Route to /bug-fix

```
MAX_ITER="${CLAUDE_BUILD_ITERATIONS:-3}"
case "$MAX_ITER" in ''|*[!0-9]*) MAX_ITER=3 ;; esac
(( MAX_ITER > 10 )) && MAX_ITER=3
# Enforced bound: 0..10 integer. Non-integer or >10 → default 3.
# =0 disables the loop entirely.
```

When the iteration counter reaches `MAX_ITER` (cap exceeded):

1. Write structured handoff to `pipeline-state/{task-id}/build-handoff.md` with sections:
   - `## Failing Tests`   (names + 20-line excerpts per iteration)
   - `## Attempted Edits` (chronological, file:line per iteration)
   - `## Hypotheses Tried` (one bullet per iteration)
   All derived from the scratchpad `test-failure-feedback` entries.
2. Emit verdict `BUILD_FAILED` with
   - `reason: iteration_cap_exhausted`
   - `handoff: pipeline-state/{task-id}/build-handoff.md`
   The orchestrator detects this verdict + reason and dispatches `/bug-fix` per `protocols/pipeline-protocol.md` § In-Cycle Fix Rule. The build agent does NOT invoke `/bug-fix` directly (Skill is in the build agent's disallowedTools).
3. Escape-hatch: `CLAUDE_BUILD_ITERATIONS=0` SKIPS the loop entirely — first RED at Step 4a writes the handoff (single entry: current failure) and emits `BUILD_FAILED reason: iteration_loop_disabled`.

The exhaustion path is NOT deferral — `/bug-fix` runs within the same pipeline per Iron Law 6.

## Step 5: Inline Code Review (mandatory before BUILD_COMPLETE)

After the self-review checklist passes, the build agent (or orchestrator on its behalf) dispatches `/code-review` inline. Code-review is no longer a separate phase boundary — it runs as the final step of Build because the value-add is "second model with different priors", not a phase gate.

Procedure:
1. Dispatch `code-reviewer` agent (read-only, no worktree) per `skills/code-review/SKILL.md`.
2. If APPROVE → emit `BUILD_COMPLETE`.
3. If CHANGES_REQUESTED → spawn `fix-engineer` on the same worktree, re-run the suite, re-dispatch `code-reviewer` with the original finding + fix diff. Max 2 rounds total. If still CHANGES_REQUESTED after 2 rounds, escalate to user.

Security review is a separate phase that runs after `BUILD_COMPLETE` — do NOT dispatch `/security-review` from inside Build.

### Step 5b: Inline Sandbox Verify (mandatory before BUILD_COMPLETE)

After Step 5 returns APPROVE, the build agent (or orchestrator on its behalf) dispatches `/sandbox-verify` inline. Step 5b is the second inline gate inside Build — it confirms the worktree's pass set reproduces inside a fresh E2B sandbox so machine-specific or "works on my worktree" patches do not reach Final Gate. Like Step 5, this is a gate inside Build, NOT a separate pipeline phase.

The build agent writes the build-phase state file `pipeline-state/{task-id}/build.md` with three append-only sections: `## Decision Record`, `## Context for Review`, and (added by Step 5b) `## Sandbox Verify`. The exact `## Sandbox Verify` section template — including its body table with columns `Test | Worktree | Sandbox | Diff` — is documented in `### Sandbox Verify Section (Mandatory After Step 5b)` below, which appears in the file AFTER the `### Context for Next Phase` subsection so Story-4 forensics can locate the block deterministically.

Procedure:
1. **State stub first** — write the `## Sandbox Verify` section header to `pipeline-state/{task-id}/build.md` BEFORE invoking the skill (state-before-expensive-op — the E2B microVM is timeout-bounded and may be killed at the wall-clock cap; the stub makes the round recoverable).
2. Dispatch `sandbox-verify-engineer` agent via `/sandbox-verify` (worktree-reuse — the engineer inherits the prior build's worktree path). The engineer parses the worktree's pytest/jest/rspec pass set, runs the same suite inside an E2B microVM, compares both pass sets, and returns one of three verdicts.
3. Branch on verdict:
   - **SANDBOX_VERIFIED** → write the final `## Sandbox Verify` body (per the template subsection below) and emit `BUILD_COMPLETE`.
   - **SANDBOX_SKIPPED** with `reason ∈ {no-e2b-token, no-testable-changes, env-hatch}` → write the `## Sandbox Verify` body noting the skip reason and emit `BUILD_COMPLETE`. The three benign skip reasons are: `no-e2b-token` (no `E2B_API_KEY` available — Story-1 path), `no-testable-changes` (docs-only diff per `git diff --name-only $BASE...HEAD` against the project's testable-paths set — Story 2), and `env-hatch` (operator set `CLAUDE_DISABLE_SANDBOX_VERIFY=1` — Story 2).
   - **SANDBOX_FAILED** → spawn `fix-engineer` on the same worktree per `protocols/pipeline-protocol.md` § In-Cycle Fix Rule, re-run the suite, then re-dispatch Step 5 code-review FIRST and Step 5b sandbox-verify SECOND with the original divergence list + fix diff. The 2-round cap is **combined with Step 5** — code-review rounds and sandbox-verify rounds share a single 2-round budget across Build (max 2 rounds total, NOT 2+2). If `current_round + 1 > 2` after a failure, escalate to the user with the divergence list. The round counter lives in the orchestrator's spawn-prompt state, NOT in `build.md` frontmatter — a `build.md` frontmatter writer would mis-persist the counter and break the combined-budget arithmetic. Round 3+ never executes inside Build.

The `Test | Worktree | Sandbox | Diff` table columns and the `## Sandbox Verify` heading itself are pinned by the template subsection below — the build agent renders the same column layout on every spawn so the Story-4 forensics consumer can join rows by test name.

**Section overwrite semantics — last-writer-wins.** Round 2's `/sandbox-verify` spawn overwrites the `## Sandbox Verify` section in `build.md` produced by round 1 — the final state file reflects the round-2 outcome, never a merge.

**Escape hatch.** Set `CLAUDE_DISABLE_SANDBOX_VERIFY=1` in the environment to skip Step 5b — `/sandbox-verify` fast-exits with `SANDBOX_SKIPPED` reason `env-hatch` and appends one JSONL line to `metrics/{session-id}/sandbox-verify-skips.jsonl`. Build then proceeds to `BUILD_COMPLETE`. The hatch matches the canonical `CLAUDE_DISABLE_*=1` shape used by `CLAUDE_DISABLE_AUTO_LEARN`, `CLAUDE_DISABLE_INSTINCT_INJECTION`, and six sibling hooks.

## Verdict

After Step 5 completes:
- **BUILD_COMPLETE**: All ACs have passing tests, cohesion-based shape rules met, ATDD audit trail visible (RED + GREEN + mutation), code-reviewer APPROVED, AND sandbox-verify returned SANDBOX_VERIFIED or SANDBOX_SKIPPED.
- **BUILD_FAILED**: Checklist items remain unresolved OR code-review never APPROVED after 2 rounds OR sandbox-verify never returned a non-FAILED verdict within the combined 2-round budget. List which items failed.

## Phase Output

```
Verdict: BUILD_COMPLETE / BUILD_FAILED
Next: /code-review + /security-review (parallel, single message)
Artifacts: [list of changed/created files]
Agent summaries: [each engineer's 2-3 sentence contribution summary]
```

### Decision Record (Mandatory)

Include a `## Decision Record` section in the pipeline state file. This travels to the reviewer so they understand *why* before reading *what*:

```markdown
## Decision Record
- **Chose**: [approach taken]
  **Over**: [alternative considered]
  **Because**: [reasoning tied to ACs, project conventions, or engineering principles]
  **Watch**: [conditions under which this choice should be revisited]
```

Every non-trivial design choice gets an entry. Trivial choices (naming, formatting) do not. The reviewer uses this to focus their review on areas of genuine uncertainty rather than re-deriving intent from the diff.

### Context for Next Phase

Include a `## Context for Review` section in the pipeline state file:

```markdown
## Context for Review
- **Uncertainty flags**: [areas where the build agent is unsure — "I chose X but Y might be better"]
- **TDD audit summary**: [N tests added, key behaviors covered, any gaps noted]
- **Learned patterns applied**: [instincts from learning/instincts/ that influenced decisions]
- **Areas needing focus**: [specific files or patterns the reviewer should scrutinize]
```

This gives reviewers a guided entry point instead of a cold diff read.

### Sandbox Verify Section (Mandatory After Step 5b)

Step 5b writes one `## Sandbox Verify` section to `pipeline-state/{task-id}/build.md`. The section appears AFTER the `## Context for Review` section so the Story-4 forensics consumer can locate the block deterministically. Round-2 overwrites round-1 (last-writer-wins).

```markdown
## Sandbox Verify
- Worktree pass: 14/15  (1 failed: test_foo_bar)
- Sandbox pass:   14/15  (1 failed: test_foo_bar)
- Verdict: SANDBOX_VERIFIED  (or SANDBOX_SKIPPED reason=... | SANDBOX_FAILED)

| Test | Worktree | Sandbox | Diff |
|---|---|---|---|
| test_foo_bar | FAIL | FAIL | match |
```

The pass counts are integer fractions (`worktree_pass / total_collected`). The `Diff` column is `match` when worktree and sandbox agree on a row's pass/fail status, and `diverge` otherwise — the SANDBOX_FAILED `diverging_tests` list is exactly the rows where `Diff` is `diverge`.

$ARGUMENTS
</reason></package>