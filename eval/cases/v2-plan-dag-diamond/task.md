# v2 Plan DAG — Diamond Parallelism Win (Synthetic)

This is a **synthetic deterministic case** that exercises v2-plan parsing
and Kahn's-algorithm wave extraction. It is the B1-fix anchor: the eval
baseline includes this case to detect regressions where the v2 dispatcher
silently serialises a parallelisable plan.

## Behaviour Under Test

Given the canonical diamond fixture at
`tests/fixtures/plan_dag/v2_diamond.md` (4 slices: `r → {a, b} → d`):

1. `parse_plan(diamond_fixture)` returns a `PlanV2` with 4 slices.
2. `topological_waves(plan)` returns 3 waves: `[[r], [a, b], [d]]`.
3. `wave_count == 3 < 4 == slice_count` — the parallelism win is observable.

## Why a Case (and Not Just a Unit Test)

The unit test in `tests/test_plan_dag_resolver.py::test_v2_diamond_yields_three_waves`
asserts the *algorithm* shape. This eval case asserts the **outcome at the
dispatcher contract layer**: parallelism actually compresses waves
(`wave_count < slice_count`). A future change to `topological_waves` that
silently regressed to chain ordering would still pass that unit test if it
carefully kept three waves in some other shape; this case keys on the
load-bearing scalar `wave_count < slice_count` so any regression that
serialises the plan trips the oracle.

## Falsifiability (B1 fix)

If a future plan change turned the diamond into a chain
(`r → a → b → d`, all serialised), `wave_count` would equal `slice_count`
(both 4), and the oracle `wave_count < slice_count` would fail. See
`tests/test_internal_eval_gate_for_dag_slice.py::EvalCaseRegressionTrips`
for the in-process demonstration of this falsifying behaviour.
