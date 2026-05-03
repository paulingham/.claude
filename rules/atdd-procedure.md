# ATDD Procedure

Full Acceptance-Test-Driven Development cycle: batched RED, mutation gate, audit trail, per-behaviour TDD exceptions. Loaded by `/build-implementation` and `/bug-fix`; not auto-loaded into every spawn. Engineering invariants (code shape, naming, testing standards, security baseline) live in `rules/engineering-invariants.md`.

## Acceptance-Test-Driven Development (ATDD) Protocol

> **IRON LAW: NO ACCEPTANCE CRITERION SHIPS WITHOUT (a) A FAILING-THEN-PASSING TEST FOR THAT AC IN THE DIFF AND (b) MUTATION SCORE >= 70% ON CHANGED LINES.**
> **IRON LAW: NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE.**

### Procedure (Exact, Auditable)

This is a step-by-step protocol, not a philosophy. Follow it literally. Three test invocations per slice — one batched RED, one post-implementation GREEN, one post-refactor GREEN. The mutation gate runs once at the end of the slice.

### Cycle (per slice, NOT per behavior)

1. **READ AC TEST STUBS**: Open `pipeline-state/{task-id}-plan.md` and pull the "Failing Test Stubs (per AC)" list the architect produced. Each stub names a test file, a test name, and an assertion intent. If any AC has no stub, halt and surface to the architect — implementation cannot begin.
2. **BATCHED RED**: Write every AC test as one batch (the architect's stubs are the contract). Run the suite ONCE. Capture the RED output (this is the audit artifact). Verify every batched test fails for the RIGHT reason — not syntax errors, not missing imports — the named behavior is absent.
3. **IMPLEMENT FREELY**: Write production code until every batched test passes. Run the suite ONCE. Capture the GREEN output. Shape constraints (8-line bodies, 50-line files, CC <= 5, nesting <= 2) apply continuously — fix as you go, not at the end.
4. **REFACTOR WHILE GREEN**: Tighten names, extract duplication (DRY on 2nd occurrence), confirm shape constraints on every touched file. Run the suite ONCE more. Capture the post-refactor GREEN output.
5. **MUTATION GATE**: Run mutation testing on changed lines (Stryker / Mutant / mutmut, or the manual fallback in `skills/verify/SKILL.md`). Score >= 70% kill rate is required. If <70%, the slice is NOT complete — go back to step 3 with targeted tests against the surviving mutations until >= 70%.

The audit trail for the slice is exactly four artifacts: the batched RED output, the post-implementation GREEN output, the post-refactor GREEN output, and the mutation report. Code-reviewer validates all four exist and that the diff contains both new tests and matching new source. Missing artifact = CHANGES_REQUESTED.

### When per-behaviour TDD Still Applies (Exceptions)

The batched-RED default does NOT apply to these cases. They keep per-behaviour RED-GREEN-REFACTOR with one test per cycle:

- **Bug fixes (always)** — the repro test IS the contract. One bug, one repro test, written and seen failing BEFORE any fix code. See `skills/bug-fix/SKILL.md`.
- **Complex algorithmic logic** — parsers, state machines, financial calculations. The cost of finding one wrong case during batched implementation outweighs the savings of batching.
- **Security-sensitive code** — auth, crypto, ACL checks. Each rule belongs to its own RED step so the failure mode is unambiguous.

For these exceptions, the cycle is the prior per-behaviour RED -> GREEN -> REFACTOR (one test, one minimum implementation, one shape pass), repeated.

### Ordering

- The architect's plan IS the implementation order: per-AC stubs are listed in dependency order. Build foundational ACs first, composed ACs last.
- Within a slice, the entire batch is RED at once, the entire batch goes GREEN at once. There is no partial-batch RED.

### ATDD Anti-Patterns (Hard Blocks)

These are NOT allowed. If you catch yourself doing any of these, STOP and correct:

- **Partial RED**: Running the suite mid-batch with only some AC tests written. The contract is the WHOLE batch — write all stubs, run once, capture RED once.
- **Skipping the mutation gate**: A green suite is not the deliverable. The mutation report is. <70% means the tests are not exercising the changed lines, regardless of what the suite says.
- **Implementing-before-RED**: Writing a single line of source before the batched-RED output is captured. The RED output is the audit artifact that proves the behaviors were absent.
- **Deferred refactoring**: Saying "I'll clean this up later." Shape constraints apply continuously, and the post-refactor GREEN is mandatory.
- **Gold plating**: Writing source that no batched test exercises. If the test isn't in the architect's stub list, it isn't load-bearing.
- **Skipping AC-stub gate**: Starting implementation when one or more ACs has no stub. Architect must produce the stub list before BUILD begins.

### Audit Trail (per slice)

The slice produces exactly four captured outputs plus the diff:

- **Batched RED output**: every AC test red, for the right reason
- **Post-implementation GREEN output**: every test green
- **Post-refactor GREEN output**: every test still green after shape pass
- **Mutation report**: kill rate >= 70% on changed lines, with surviving-mutation list (or "0 survivors")

The code-reviewer validates all four artifacts exist and the diff contains both new tests and matching new source. Missing artifact = CHANGES_REQUESTED.

## Per-Behaviour TDD: Red-Green-Refactor (Exception cases only — see § When per-behaviour TDD Still Applies)

1. **RED**: Failing test first. Verify it fails for the right reason.
2. **GREEN**: Minimum code to pass.
3. **REFACTOR**: Clean up while green.

Never skip RED — if you didn't see it fail, you don't know the test works. This three-step cycle applies to bug fixes, complex algorithmic logic, and security-sensitive code. All other slices use the batched ATDD cycle above.
