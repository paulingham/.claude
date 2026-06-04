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
4. **MUTATION GATE**: Run mutation testing on changed lines (Stryker / Mutant / mutmut, or the manual fallback in `skills/verify/SKILL.md`). Score >= 70% kill rate is required. If <70%, the slice is NOT complete — go back to step 3 with targeted tests against the surviving mutations until >= 70%.

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
- **Skipping the mutation gate**: A green suite is not the deliverable. The mutation report is. <70% means the tests are not exercising the changed lines, regardless of what the suite says.
- **Implementing-before-RED**: Writing a single line of source before the batched-RED output is captured. The RED output is the audit artifact that proves the behaviors were absent.
- **Deferred cleanup**: Saying "I'll clean this up later." Cohesion rules and DRY apply continuously *during* IMPLEMENT — not in a separate pass.
- **Gold plating**: Writing source that no batched test exercises. If the test isn't in the architect's stub list, it isn't load-bearing.
- **Skipping AC-stub gate**: Starting implementation when one or more ACs has no stub. Architect must produce the stub list before BUILD begins.

### Audit Trail (per slice)

The slice produces exactly three captured outputs plus the diff:

- **Batched RED output**: every AC test red, for the right reason
- **GREEN output**: every test green, with cohesion-compliant code (no separate post-refactor pass)
- **Mutation report**: kill rate >= 70% on changed lines, with surviving-mutation list (or "0 survivors")

The code-reviewer validates all three artifacts exist and the diff contains both new tests and matching new source. Missing artifact = CHANGES_REQUESTED.

## Per-Behaviour TDD (Exception cases only — see § When per-behaviour TDD Still Applies)

1. **RED**: Failing test first. Verify it fails for the right reason.
2. **GREEN**: Minimum cohesive code to pass — clean on the first pass, not a separate cleanup step.

Never skip RED — if you didn't see it fail, you don't know the test works. This two-step cycle applies to bug fixes, complex algorithmic logic, and security-sensitive code. All other slices use the batched ATDD cycle above. The per-behaviour cycle previously had a third REFACTOR step (removed alongside the batched cycle's REFACTOR step in May 2026 for the same reason).
