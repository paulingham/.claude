# Renders a regression.json payload as markdown.
def row_or_none(rows):
  if (rows|length)==0 then "_None._"
  else (rows|map("- \(.case_id): \(.baseline_status) → \(.current_status)")|join("\n"))
  end;
def list_or_none(lst):
  if (lst|length)==0 then "_none_" else (lst|join(", ")) end;

"# Regression Report",
"",
"**Verdict**: \(.verdict)  |  **Regressions**: \(.regression_count)  |  **Intersection**: \(.intersection_count)",
"",
"- Baseline harness: \(.baseline_harness_ref)",
"- Current harness:  \(.run_harness_ref)",
"",
"## Regressions (pass → fail)",
row_or_none(.regressions),
"",
"## Improvements (fail → pass)",
row_or_none(.improvements),
"",
"## Added / Removed (neutral)",
"- Added:   \(list_or_none(.added))",
"- Removed: \(list_or_none(.removed))"
