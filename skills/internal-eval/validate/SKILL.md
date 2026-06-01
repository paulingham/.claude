---
name: "internal-eval-validate"
description: "Delivery validation for /harness:internal-eval: proves the baseline → inject → diff → restore → confirm-clean flow end-to-end with a stubbed inner pipeline. Runs locally and in CI; does NOT execute real /harness:pipeline cases."
context: fork
agent: qa-engineer
argument-hint: "[tmp-dir]"
---

# Internal Eval — Delivery Validation

## What This Skill Does

Demonstrates that the /harness:internal-eval flow correctly detects regressions. The
sequence runs in five phases:

1. **Phase A — Baseline**: seed 3 deterministic cases, run-suite with the
   stub manifest empty (all cases pass), capture-baseline, assert
   `pass_rate == 1.00`.
2. **Phase B — Inject**: flip ≥2 cases in the stub manifest to `fail`,
   re-run at a new run-id, rewrite `failed_build` → `failed_diff` to match
   oracle-rejection semantics, re-aggregate.
3. **Phase C — Diff**: run `diff-vs-baseline.sh`, assert
   `verdict == "EVAL_FAILED"`, `regression_count ≥ 2`, and that both
   flipped case-ids appear in the `regressions` quadrant.
4. **Phase D — Restore**: revert the stub manifest, re-run at a third
   run-id. Byte-equivalence check: `shasum agents/code-reviewer.md` before
   and after MUST match (the live harness is never touched).
5. **Phase E — Confirm clean**: run `diff-vs-baseline.sh` on the restored
   run, assert `verdict == "EVAL_PASSED"` and `regression_count == 0`.

The driver exits 0 only when all five phases pass. Any assertion failure
exits non-zero with a descriptive stderr line.

## Why a Stubbed Inner Pipeline

A real live-harness eval run costs hours of wall-clock and real API spend
per case — out of scope for a build-phase deliverable. This sequence
proves the FLOW (seed → run → score → diff → gate) using
`EVAL_INNER_STUB`, the same extension point the Story 6 contract defines.
The stub reads a JSON manifest (`{case-id: "pass"|"fail"}`) and exits with
the corresponding rc. Flipping the manifest is deterministic, hermetic,
and reversible — unlike mutating `agents/code-reviewer.md` directly, which
would risk contaminating the live harness mid-test.

Live-harness baseline capture is a separate **ship-phase activity**: the
first real baseline is stamped by `/harness:pr-creation` against `main` after the
internal-eval harness is merged.

## Usage

```
bash skills/internal-eval/validate/run-validation-sequence.sh [tmp-dir]
```

If `tmp-dir` is omitted, a fresh `mktemp -d` is used. The directory is
kept on exit so you can inspect `runs/*/aggregate.json`,
`runs/*/regression.json`, and `baselines/` after a failure.

## Artifacts

```
skills/internal-eval/validate/
├── SKILL.md                 (this file)
├── run-validation-sequence.sh   (entry — the 5-phase driver)
└── lib/
    ├── stub-manifest.sh     (EVAL_INNER_STUB — reads manifest, exits rc)
    ├── seed.sh              (seeds 3 deterministic cases)
    ├── phase-runners.sh     (phase_a..phase_e)
    ├── phase-io.sh          (run-suite / capture-baseline / diff wrappers)
    ├── phase-mutate.sh      (rewrites failed_build → failed_diff + reaggregate)
    ├── assertions.sh        (pass_rate / verdict / regression_count / bytes-equal)
    └── sequence-asserts.sh  (composed per-phase assertion bundles)
```

## Verdict

| Exit Code | Meaning |
|---|---|
| `0` | All five phases passed; flow is correct. |
| non-zero | An assertion failed; see stderr for the phase + specific assertion. |

## Prerequisite

- Story 6 `EVAL_INNER_STUB` contract in place (always).
- `jq` and `shasum` available on `$PATH`.
- The live harness is untouched by this script — run from any checkout.
