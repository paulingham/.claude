# Expected Behaviours — v2 Plan DAG Diamond Parallelism

## Required Behaviours

1. `parse_plan("tests/fixtures/plan_dag/v2_diamond.md")` returns a `PlanV2`
   instance with `slice_count == 4`.
2. `topological_waves(plan)` returns a `list[list[str]]` of length 3
   (`wave_count == 3`), where:
   - `waves[0]` is `["r"]`
   - `waves[1]` (sorted) is `["a", "b"]`
   - `waves[2]` is `["d"]`
3. The B1-fix oracle holds: `wave_count == 3` AND `slice_count == 4` AND
   `wave_count < slice_count`.

## Required Oracle Tests (must be green on candidate diff)

These pytest node IDs MUST be green when the harness runs the candidate's
diff. Each maps to one required behaviour above.

- `tests/test_plan_dag_resolver.py::TopologicalWavesFixtures::test_v2_diamond_yields_three_waves`
- `tests/test_internal_eval_gate_for_dag_slice.py::EvalCaseOracleAssertsWaveCountLessThanSliceCount::test_diamond_wave_count_is_three_and_less_than_slice_count`
- `tests/test_internal_eval_gate_for_dag_slice.py::EvalCaseRegressionTrips::test_chain_plan_with_four_slices_produces_four_waves`

## Falsifying Conditions

The oracle FAILS (case status `failed_diff`) if any of:

- `parse_plan` returns `ValidateResult(ok=False, ...)` on the diamond fixture.
- `topological_waves` returns `wave_count != 3`.
- `wave_count >= slice_count` (parallelism regression — the B1-fix anchor).
- The diamond fixture changes shape such that
  `topological_waves(plan) != [["r"], ["a", "b"], ["d"]]` (modulo within-wave
  sort order).
