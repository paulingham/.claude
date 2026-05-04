---
category: decision
---

HIGH finding (Step 7c referenced fictional `phases.build.agents[].role` path) was fixed via option (b) — extending the observation schema example at `rules/_detail/autonomous-intelligence.md` § Observation Capture so `phases.build.agents` is documented as an array of `{role, model}` objects. This aligns with B12.2's per-(role, task-class) aggregation goal — the integer-count form would have made the primary group-key extraction permanently fictional. A new Field reference table row pins the contract so future readers cannot drift back to the integer form by accident.

---
category: decision
---

MEDIUM finding (Step 7c referenced undocumented `phases.verify.mutation_score`) was fixed alongside the HIGH by adding `mutation_score: 0.78` to the verify entry in the example record AND a Field reference row that ties the field back to Iron Law 1 (≥0.70 mutation kill-rate on changed lines). Absence-tolerance language matches the existing `cost_estimate_usd` precedent.

---
category: pattern
---

Helper-scoping pattern (`_learn_section_outside_step_1_and_10`) — for tests that assert keyword presence in markdown step bodies, slice the file to the enclosing `### N[x]. ...` step using header-position math. Returning the full file when the needle is "outside the forbidden steps" makes downstream `assertRegex` calls match unrelated mentions in other steps and weakens the test. Slice to `[enclosing_start:next_start]` instead.

---
category: warning
---

Stale `metrics/{session}/subagent-runtimes/*.start` files from prior sessions can block bash invocations via `runtime-guard.sh` Mode B (global scan) when this fix-engineer is dispatched into a long-lived sandbox. Cleanup pattern that worked: `/usr/bin/find $METRICS -name '*.start' -mmin +60 -delete`. The orchestrator should consider periodic pruning, or `subagent-stop-trajectory.sh` should be checked for missed cleanup paths on session crash.

---
category: discovery
---

Test invocation gotcha: `pytest` and `python` (without `3`) are not on PATH in this sandbox; only `/opt/homebrew/bin/python3` resolves. Tests under `tests/` import directly from `hooks/_lib/*.py` modules — must set `PYTHONPATH=hooks/_lib`. There is no `conftest.py` or `pyproject.toml` in the repo root, so this is implicit project convention. Three pre-existing collection errors (`test_advisor_resolver.py`, `test_agent_frontmatter_io.py`, `tests/integration/test_planning_agent_lifecycle.py`) reference modules not present in `hooks/_lib/` — these are pre-existing baseline failures, not caused by this fix.
