# Computes 4 quadrants from baseline + current aggregate JSON.
# Inputs: $base (baseline JSON), $cur (current aggregate JSON).
# Rules:
#   regressions:  passed   → NOT passed (failed_diff/failed_build)
#   improvements: !passed  → passed
#   removed:      in baseline, not in current
#   added:        in current, not in baseline
# failed_infra and failed_timeout are NEUTRAL — skipped from regression math.
# Intersection applies before regression/improvement compute (caller filters $cur).

def by_id(list): list | map({key:.case_id, value:.status}) | from_entries;
def is_infra_neutral(s): s == "failed_infra" or s == "failed_timeout";

($base | by_id(.cases))                           as $b
| ($cur | by_id(.case_results // []))             as $c
| ($b | keys)                                     as $bk
| ($c | keys)                                     as $ck
| [$bk[] | select(. as $k | $ck | index($k))]     as $intersection
| {
    regressions: [$intersection[]
      | . as $k
      | select($b[$k] == "passed" and $c[$k] != "passed" and (is_infra_neutral($c[$k]) | not))
      | {case_id:$k, baseline_status:$b[$k], current_status:$c[$k]}],
    improvements: [$intersection[]
      | . as $k
      | select($b[$k] != "passed" and $c[$k] == "passed")
      | {case_id:$k, baseline_status:$b[$k], current_status:$c[$k]}],
    removed:  [$bk[] | select(. as $k | $ck | index($k) | not)],
    added:    [$ck[] | select(. as $k | $bk | index($k) | not)],
    intersection_count: ($intersection | length)
  }
