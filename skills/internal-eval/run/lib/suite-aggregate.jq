# Aggregates an array of per-case result.json objects into aggregate.json.
# Input: slurped array of result objects. Args: $run_id, $suite, $model, $harness, $ts.
(map(select(.status == "passed")) | length)        as $passed
| (map(select(.status == "failed_diff")) | length)   as $failed_diff
| (map(select(.status == "failed_build")) | length)  as $failed_build
| (map(select(.status == "failed_timeout")) | length) as $failed_timeout
| (map(select(.status == "failed_infra")) | length)  as $failed_infra
| length                                             as $total
| ($total - $failed_infra)                           as $denom
| (if $denom > 0 then ($passed / $denom) else 0 end) as $rate
| (map(.cost_usd // 0) | add // 0)                   as $cost
| (map(.duration_sec // 0) | add // 0)               as $dur
| {
    run_id: $run_id, suite: $suite, model: $model, harness_ref: $harness,
    total_cases: $total, passed: $passed,
    failed_diff: $failed_diff, failed_build: $failed_build,
    failed_timeout: $failed_timeout, failed_infra: $failed_infra,
    pass_rate: $rate, total_duration_sec: $dur, total_cost_usd: $cost,
    completed_at: $ts,
    case_results: map({case_id, status})
  }
