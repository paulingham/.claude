# ATDD Procedure

Full Acceptance-Test-Driven Development cycle: batched RED, single GREEN, mutation gate, audit trail, per-behaviour TDD exceptions. Loaded by `/harness:build-implementation` and `/harness:bug-fix`; not auto-loaded into every spawn. Engineering invariants (code shape, naming, testing standards, security baseline) live in `protocols/engineering-invariants.md`.

## Acceptance-Test-Driven Development (ATDD) Protocol

> **IRON LAW: NO ACCEPTANCE CRITERION SHIPS WITHOUT (a) A FAILING-THEN-PASSING TEST FOR THAT AC IN THE DIFF AND (b) MUTATION SCORE >= 70% ON CHANGED LINES.**
> **IRON LAW: NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE.**

### Procedure (Exact, Auditable)

This is a step-by-step protocol, not a philosophy. Follow it literally. Two test invocations per slice — one batched RED, one GREEN. The mutation gate runs once at the end of the slice. Cohesion and DRY are enforced *during* IMPLEMENT, not in a separate refactor pass.

### Cycle (per slice, NOT per behavior)

1. **READ AC TEST STUBS**: Open `$state_dir/{task-id}-plan.md` and pull the "Failing Test Stubs (per AC)" list the architect produced. Each stub names a test file, a test name, and an assertion intent. If any AC has no stub, halt and surface to the architect — implementation cannot begin.
2. **BATCHED RED**: Write every AC test as one batch (the architect's stubs are the contract). Run the suite ONCE. Capture the RED output (this is the audit artifact). Verify every batched test fails for the RIGHT reason — not syntax errors, not missing imports — the named behavior is absent.
3. **IMPLEMENT CLEANLY**: Write production code that is correct AND well-shaped on the first pass. Cohesion rules (one-thing-per-function, CC ≤ 5, nesting ≤ 2, DRY on 2nd occurrence — see `protocols/engineering-invariants.md` § Code Shape) apply *as you write*, not in a separate cleanup pass. Choose intent-revealing names from the start; extract duplication on the 2nd occurrence as it appears. Run the suite ONCE when done. Capture the GREEN output.
4. **MUTATION GATE — Active, Time-Boxed Mutation Kill Loop**: Run mutation testing on changed lines (Stryker / Mutant / mutmut, or the manual fallback in `skills/verify/SKILL.md`). Score >= 70% kill rate on changed lines is required. If <70%, the slice is NOT complete — run the **Mutation Kill Loop** below until the rate reaches >= 70%, the wall-clock budget is spent, or no progress can be made.

#### Mutation Kill Loop

**Env knob.** `CLAUDE_MUTATION_KILL_BUDGET_SECONDS`, default **300**. Sanitiser: positive integer required; non-integer or negative value → use default 300. **Minimum floor**: any value < 120 coerces up to 120 (footgun guard — a budget below the mutation tool's own runtime would exit `EXHAUSTED` at round 1 with zero kill-rounds; the floor guarantees at least one full round can complete).

**`=0` is NOT a disable hatch.** This knob deliberately **diverges** from the `CLAUDE_BUILD_ITERATIONS` sanitiser (`build-implementation` Step 4c, where `=0` disables the build-feedback loop entirely). Here, `=0` is **NOT** an escape hatch: the >= 70% changed-lines mutation gate is **Iron Law 1** and **cannot be disabled by any env value**. `=0` is a non-negative integer < 120, so the floor rule fires: `0 → 120` (NOT 300). The `→ 300` path applies only to negative or non-integer values (use default 300). Deterministically: `0 → 120` (floor); negative or non-integer → 300 (default). The loop always runs and the gate always applies. An engineer must never read `=0` as "skip the loop": that would bypass an Iron-Law gate.

**Start-time stamp.** Stamp `KILL_LOOP_START=$(date +%s)` **once**, immediately **before the first mutation run** that establishes the baseline (on first entry to step 4 for the slice). The stamp is checked at the **top of every round** before authoring more kill-tests: `elapsed >= budget` → exit `EXHAUSTED`. The stamp is NOT persisted to a state file (no resume semantics — a crashed Build slice restarts the loop fresh).

**Round body (per round) — ORDER IS LOAD-BEARING:**

1. **Budget check** — if `elapsed >= budget` → exit `EXHAUSTED`. (Top of every round, before any authoring.)
2. **Read survivors** — parse the latest mutation-report section; filter to surviving mutants whose `file:line` is on changed lines; drop `equivalent: yes` mutants (excluded from denominator).
3. **No-progress check** — if this is round >= 2 AND the prior round killed zero AND this round's survivor set is unchanged → increment the zero-kill counter; two consecutive zero-kill rounds → exit `NO_PROGRESS`. **This check runs BEFORE authoring** so a met no-progress condition does not waste a full author + re-run cycle.
4. **Author kill-tests** — targeted tests against the surviving changed-line mutants (boundary swap, comparator flip, etc. as the surviving operator indicates). RED-then-GREEN per the per-behaviour audit contract.
5. **Re-run mutation testing** on changed lines; compute kill rate = killed / (killed + survived), denominator excluding `equivalent: yes`.
6. **Append** a `### Kill-Loop Round N` section to the single mutation-report artifact (see Append Structure below).
7. **Exit check** — kill rate >= 70% → exit `REACHED`; else loop to step 1.

> Canonical ordering, stated explicitly so a verbatim implementer cannot reorder it:
> **budget check → read survivors → NO_PROGRESS check → author → re-run → append → REACHED check → loop.**

**Equivalent-mutant handling.** A mutant judged semantically equivalent (behaviour-preserving, no test can distinguish it) is flagged `equivalent: yes` with a one-line rationale and **excluded from the kill-rate denominator** — identical to the Tier 3.5 equivalence filter in `skills/verify/SKILL.md` § 4.25 step 3. `unsure` defaults to inclusion (counts against the rate). code-reviewer + patch-critic spot-check equivalence rationales.

**Exit outcomes.**

- `REACHED` (>= 70%) — slice continues normally; OUTCOME=`REACHED` recorded in the report header.
- `EXHAUSTED` (wall-clock spent, <70%) — slice NOT complete. The existing gate fails. Hand-back bundle (same worktree, same pipeline): residual surviving changed-line mutants, the kill-tests already authored this loop (committed, not discarded), and any `equivalent`/`unsure` flags.
- `NO_PROGRESS` (two consecutive zero-kill rounds, <70%) — identical hand-back to `EXHAUSTED`; OUTCOME=`NO_PROGRESS`. Distinguished from `EXHAUSTED` only so forensics can tell "ran out of time" from "stuck".

**Recovery action on `EXHAUSTED`/`NO_PROGRESS`.** Fails the Build gate and triggers the standard in-cycle fix path (Iron Law 6): a fix-engineer on the **same worktree** continues from the residual survivor set. The already-authored kill-tests **persist** — they were committed during the loop and are NOT discarded. On re-entry, `KILL_LOOP_START` **resets** (re-stamped before the first re-entry mutation run) and the wall-clock budget resets to its full value. The residual is **NEVER deferred as a follow-up ticket** — that would violate Iron Law 6.

**Append structure (audit-trail preservation).** The slice has exactly one mutation-report artifact. The kill loop appends BELOW the Tier-3 baseline and ABOVE any Tier-3.5 verify sections (written later at Final Gate). Structure:

```
## Mutation Report (slice <id>)
- OUTCOME: REACHED | EXHAUSTED | NO_PROGRESS
- Final kill rate: <killed>/<killed+survived> = <pct>% (equivalents excluded: <n>)
- Budget: <elapsed>s / <effective budget after floor/default>s

### Baseline (Tier 3, pre-loop)
- kill rate, surviving-mutant list (file:line:operator)

### Kill-Loop Round 1
- tests added, kill rate after, survivors remaining
### Kill-Loop Round N
- ...

<!-- Tier 3.5 verify sections, if any, appended BELOW the last Kill-Loop round at Final Gate -->
```

Rounds are append-only — never rewrite a prior round. The OUTCOME header is the single last-writer-wins field, set on loop exit. This preserves the locked 3-artifact count: the single mutation-report artifact gains sections, never spawning a second file.

> **Note on Tier 3.5 at Final Gate.** Because Kill-Loop rounds sit between the Tier-3 baseline and the (later) Tier-3.5 sections, `skills/verify/SKILL.md` § 4.25 dedups against the **latest Kill-Loop round's** survivor list (not the stale Tier-3 baseline) and appends **below any Kill-Loop rounds**. See § 4.25 for the full procedure.

The audit trail for the slice is exactly three artifacts: the batched RED output, the GREEN output, and the mutation report. Code-reviewer validates all three exist and that the diff contains both new tests and matching new source. Missing artifact = CHANGES_REQUESTED.

The previous "REFACTOR while green" step (separate pass, fourth audit artifact) was removed in May 2026. AI agents can write cohesive, well-named code on the first pass; the separate refactor invocation existed because human authors cannot hold correctness and structure in working memory simultaneously. Cohesion is now enforced continuously during step 3, and the post-cleanup GREEN capture is no longer required.

### When per-behaviour TDD Still Applies (Exceptions)

The batched-RED default does NOT apply to these cases. They keep per-behaviour RED-GREEN with one test per cycle:

- **Bug fixes (always)** — the repro test IS the contract. One bug, one repro test, written and seen failing BEFORE any fix code. See `skills/bug-fix/SKILL.md`.
- **Complex algorithmic logic** — parsers, state machines, financial calculations. The cost of finding one wrong case during batched implementation outweighs the savings of batching.
- **Security-sensitive code** — auth, crypto, ACL checks. Each rule belongs to its own RED step so the failure mode is unambiguous.

For these exceptions, the cycle is per-behaviour RED -> GREEN (one test, one minimum cohesive implementation), repeated. The separate refactor step was removed in May 2026 — cohesion is enforced *during* GREEN.

### Ordering

- The architect's plan IS the implementation order: per-AC stubs are listed in dependency order. Build foundational ACs first, composed ACs last.
- Within a slice, the entire batch is RED at once, the entire batch goes GREEN at once. There is no partial-batch RED.

### ATDD Anti-Patterns (Hard Blocks)

These are NOT allowed. If you catch yourself doing any of these, STOP and correct:

- **Partial RED**: Running the suite mid-batch with only some AC tests written. The contract is the WHOLE batch — write all stubs, run once, capture RED once.
- **Skipping the mutation gate or the Kill Loop**: A green suite is not the deliverable. The mutation report with OUTCOME recorded is. <70% means the tests are not exercising the changed lines, regardless of what the suite says. The Mutation Kill Loop is the active remediation path — skipping it bypasses Iron Law 1.
- **Implementing-before-RED**: Writing a single line of source before the batched-RED output is captured. The RED output is the audit artifact that proves the behaviors were absent.
- **Deferred cleanup**: Saying "I'll clean this up later." Cohesion rules and DRY apply continuously *during* IMPLEMENT — not in a separate pass.
- **Gold plating**: Writing source that no batched test exercises. If the test isn't in the architect's stub list, it isn't load-bearing.
- **Skipping AC-stub gate**: Starting implementation when one or more ACs has no stub. Architect must produce the stub list before BUILD begins.

### Audit Trail (per slice)

The slice produces exactly three captured outputs plus the diff:

- **Batched RED output**: every AC test red, for the right reason
- **GREEN output**: every test green, with cohesion-compliant code (no separate post-refactor pass)
- **Mutation report**: kill rate >= 70% on changed lines, with OUTCOME field (`REACHED`/`EXHAUSTED`/`NO_PROGRESS`) and surviving-mutation list (or "0 survivors"). Includes one `### Kill-Loop Round N` section per kill-loop round run during Build (append-only, never clobber).

The code-reviewer validates all three artifacts exist and the diff contains both new tests and matching new source. Missing artifact = CHANGES_REQUESTED.

## Per-Behaviour TDD (Exception cases only — see § When per-behaviour TDD Still Applies)

1. **RED**: Failing test first. Verify it fails for the right reason.
2. **GREEN**: Minimum cohesive code to pass — clean on the first pass, not a separate cleanup step.

Never skip RED — if you didn't see it fail, you don't know the test works. This two-step cycle applies to bug fixes, complex algorithmic logic, and security-sensitive code. All other slices use the batched ATDD cycle above. The per-behaviour cycle previously had a third REFACTOR step (removed alongside the batched cycle's REFACTOR step in May 2026 for the same reason).
