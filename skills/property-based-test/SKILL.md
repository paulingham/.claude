---
name: "property-based-test"
description: "Build-phase utility skill: spawn pbt-engineer to author Tier 1.5 property-based tests for changed-line public functions with typed signatures. Time-box 60s/function. Frozen counterexamples freeze inline as deterministic Tier 1 tests using harness-native syntax. Auto-invoked from /build-implementation Step 1d."
context: fork
agent: pbt-engineer
---

# Property-Based Test

## What This Skill Does

Authors **Tier 1.5 property-based tests** (per `rules/_detail/engineering-invariants.md` § Proof of Correctness) for every public function on changed lines with a typed signature. Spawns a `pbt-engineer` agent in the calling Build engineer's worktree (no fresh worktree — mirrors `fix-engineer`). For each candidate function the engineer generates ≥1 property using a harness-native PBT framework, time-boxes work at 60s/function, and freezes any counterexamples inline as deterministic regression tests. Output files match the existing `tests/**/*.property.{spec,test}.*` glob byte-for-byte so `build-implementation:94` Step 2b cap-detection (5→3) fires automatically.

## When to Invoke

- Build-phase utility, called from `/build-implementation` **Step 1d** (between Step 1c contract assertions and Step 2 batched RED).
- Auto-invoked on every Build run unless `CLAUDE_PBT=0`.
- Never invoked from Final Gate — `/qa-test-strategy` at Final Gate VERIFIES the coverage matrix; it does not author.

## Procedure

### 1. Identify candidate functions

Read `git diff --name-only` against the base branch. For each changed file, list public functions on changed lines that have typed signatures (type annotations / type hints / TypeScript type sigs / Erlang specs / etc.). Candidates are exactly those public-typed functions.

If the candidate list is empty → emit `PBT_SKIPPED (no-candidates)` and proceed.

### 2. Pick the PBT framework per language

Use the **Language → PBT Framework** table below to select the harness for each candidate's host language. If a candidate's language has no shipped harness in the table (or the named harness is not installed in the worktree), emit `PBT_SKIPPED (no-framework-for-language)` for that candidate and continue with the others — do NOT emit `PBT_BLOCKED`.

| Language | PBT framework | Notes |
|---|---|---|
| Python | Hypothesis | `@given` + `@example` |
| TypeScript / JavaScript | fast-check | `fc.assert(fc.property(...))` |
| Erlang | PropEr | `?FORALL` |
| Haskell | Hedgehog or QuickCheck | either accepted |
| Scala / Kotlin / JVM | ScalaCheck or Hypothesis-jvm | either accepted |
| Go | (none shipped) | emit PBT_SKIPPED (no-framework) |
| Rust | proptest (if present) | else PBT_SKIPPED (no-framework) |
| Swift | (none shipped) | emit PBT_SKIPPED (no-framework) |
| Plain Bash / shell | (N/A — no typed signatures) | emit PBT_SKIPPED (no-candidates) |

### 3. Generate ≥1 property using one of four canonical relations

Pick the strongest applicable relation for each candidate (≥1 required):

- **Idempotence** — `f(f(x)) == f(x)` (e.g., `normalize`, `sanitize`, `dedupe`).
- **Inverse** — `decode(encode(x)) == x` and `encode(decode(y)) == y` for round-trippable pairs.
- **Oracle** — `f(x)` agrees with a known reference implementation (slower but obviously correct version) on all inputs.
- **Metamorphic** — relations between outputs, e.g. `f(sort(xs)) == sort(f(xs))`, `f(x ++ y) == f(x) + f(y)` for homomorphisms, `f(x) ⊆ f(x ++ y)` for monotonicity.

If no relation applies (I/O-only functions, pure SDK pass-throughs, single-call dispatchers), record a one-line **impossibility justification** instead of generating a property. The justification names the impossibility class. Example: `dispatchSdkCall — justified-impossible: pure SDK pass-through`.

### 4. Time-box 60s per function

Wall-clock cap per candidate. If the harness exhausts the budget without finding a counterexample, record `passed_within_budget` and move on. If a counterexample IS found, freeze it.

### 5. Freeze counterexamples inline (harness-native syntax)

Every counterexample produced by the PBT harness becomes a deterministic regression test in the same property-test file. Use harness-native replay syntax — co-located with the property the counterexample falsified:

- **Hypothesis** — `@example(...)` decorator stacked above the `@given(...)` call. Once frozen, append-only — do NOT re-freeze the same logical case on re-runs (Hypothesis re-shrinks).
- **fast-check** — seeded `fc.assert(fc.property(...), { seed: 0xab12, examples: [[ ... ]] })` with the shrunk seed and the example array.
- **PropEr / Erlang** — frozen `?FORALL` with the stored seed in the same module.

### 6. Write the property file

The output file MUST match the canonical glob byte-for-byte:

```
tests/**/*.property.{spec,test}.*
```

This is the same glob `skills/build-implementation/SKILL.md` line 94 uses for Step 2b cap-detection. Mutating either copy of the glob breaks cap-reduction silently.

### 7. Commit alongside the build engineer's diff

The pbt-engineer reuses the calling Build engineer's worktree — frozen tests and properties commit in the same branch as the production change.

## Verdict

The skill emits exactly one of three top-level verdicts.

### `PBT_AUTHORED`

≥1 property authored, ≥0 counterexamples frozen, ≥0 functions justified-impossible. Build proceeds.

### `PBT_SKIPPED`

Skill exited cleanly without authoring. Build proceeds. The reason code distinguishes three benign skip paths:

- `env-hatch` — `CLAUDE_PBT=0` was set; skill fast-exited before identifying candidates.
- `no-candidates` — no public-typed-changed-line functions found in the diff (e.g., docs-only change, plain Bash work).
- `no-framework-for-language` — candidate's language has no shipped PBT harness in the language table, or the named harness is not installed in the worktree.

### `PBT_BLOCKED`

Skill hit a non-recoverable failure on a candidate. Build halts and surfaces the failure to the orchestrator. Two reason codes:

- `harness-crash` — the underlying PBT framework (Hypothesis, fast-check, PropEr, …) crashed in a way the engineer cannot route around.
- `unrecoverable-error` — any other non-recoverable error path (e.g., disk-full while writing the property file, permission denied, infinite loop in strategy generation that exceeded the 60s wall-clock with no usable result).

#### `PBT_BLOCKED` operator-visible payload

When emitting `PBT_BLOCKED`, include in the verdict payload:

- The **candidate function name** (fully qualified: `path/to/file.py::function_name` or language equivalent — e.g., `lib/url.ts::normalizeUrl`).
- The first **5 line** excerpt of the underlying tool failure (Hypothesis traceback / fast-check error / PropEr crash report). Truncate to the first five lines so the operator surface is bounded.
- The recommended **recovery action**: *set `CLAUDE_PBT=0` in the env and re-run `/build-implementation`; do NOT retry pbt-engineer on the same function within this pipeline*.
- An explicit statement that **`PBT_BLOCKED` does NOT count against the retry-twice-then-escalate budget** in `rules/_detail/operational-protocol.md` because the env hatch is a single-action recovery; the orchestrator-side retry counter resets when `CLAUDE_PBT=0` is set.

## Escape Hatch

**Escape hatch.** Set `CLAUDE_PBT=0` in the environment to disable Step 1d — this skips PBT authoring entirely. The hatch exists for the soak window (default-on) so cycle-time impact can be measured before flipping to mandatory; it is the one-line revert path if pbt-engineer introduces unexpected runtime cost.

## Discipline

- **passes-immediately property = delete.** A property whose first run is GREEN with no harness-side shrinking has no diagnostic value. Delete it and pick a different relation, or record an impossibility justification.
- **never re-freeze the same logical case.** Hypothesis re-shrinks; if a re-run produces a different `@example` for the same logical bug, treat it as already-frozen.
- **HALT on contract gap.** If a property surfaces behavior the AC does not specify (e.g., what should happen on negative input when the AC is silent), HALT and surface to the architect. The engineer owns the implementation; the architect owns the spec.

## Tier Mapping

PBT tests run as **Tier 1.5** in `rules/_detail/engineering-invariants.md` § Proof of Correctness. They sit between unit (Tier 1) and integration (Tier 2). Frozen counterexamples join Tier 1.

## Reference

- arXiv **2510.09907** — *PBT harness for AI-authored code*. The 60s/function time-box, the four-relation rubric, the harness-native freeze syntax requirement, and the inline-counterexample idiom all derive from this paper. Future readers can locate the source via the arXiv id.

## Phase Output

```
Verdict: PBT_AUTHORED | PBT_SKIPPED ({reason}) | PBT_BLOCKED ({reason})
Candidates: N
Properties authored: N
Counterexamples frozen: N
Justifications recorded: N
```
