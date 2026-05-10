# Patterns & Conventions
_Code patterns in use (service objects, barrel exports, hook composition). Naming conventions. Architecture decisions observed. Framework-specific idioms. Session discoveries: gotchas encountered, surprising behavior, solutions to problems. Agent effectiveness: what approaches worked well, what wasted time._

## DAG plans + bounded-wave dispatch (schema v2)
- `agents/architect.md` Artifact 5 documents `schema_version: 2` with per-slice `id` + `depends-on`; `orchestrator/parallel-dispatch-details.md § Multi-Slice DAG Mode` consumes via Kahn's topo waves. v2 plans use per-slice `### Slice <id>` stub headings; v1 retains flat layout.
- Build dispatches via canonical `pack_wave()` knapsack (NOT divisor) over `min(CLAUDE_BUILD_WAVE_MAX_PARALLEL, CLAUDE_BESTOFN_MAX_WORKTREES)`.
- Multi-slice cherry-pick: each worktree cherry-picks transitive ancestor SHAs in topo order from architect's commit. Diamond DAGs safe — git diff-vs-source-parent semantics apply R exactly once even when both A and B depend on R. Reinforces 0.50-conf cherry-pick instinct.

## Heavy-gate plan-validation challenger patterns
- Challengers consistently flag: (a) hand-waved alternatives (need ≥3/decision with verbatim citations), (b) missing failure-mode tables (need ≥6 modes incl. user-visible), (c) ROI claims without measurement (need observation fields w/ absence-tolerance + canary tests), (d) DUAL_PATH soaks proposed as ONE_SHOT (always propose DUAL_PATH from Round 1).

## Tier 1.5 PBT fallback when Hypothesis unavailable
- Deterministic seeded `random.Random(<fixed-seed>)` over 50 samples × 5 properties works. Forward-compat: swap `@given(plans())` later. 100% mutation kill achievable with manual mutation tests under `.claude-scratch-tools/`.

## Python helper module pattern
- `hooks/_lib/plan_dag_resolver.py` + `plan_dag_validation.py` join `cost_estimator.py`, `thinking_resolver.py`, `instinct_loader.py` cohort. Python is the harness's chosen language for testable algorithms (Kahn's, DAG validation, ISO 8601). Bash wrapper unnecessary when no shell consumer exists.

## Code-shape sibling extraction
- When `hooks/_lib/<m>.py` nears 300-line cap, extract cohesion-driven sibling. Parent re-exports via `from <sibling> import ...` + `# noqa: F401` for back-compat.

## Persona-categorical role tokens
- `agents/patch-critic.md::instinct_categories` = `[patch-critic, patch-critic-correctness, patch-critic-regression, patch-critic-scope, code-reviewer]`. Persona-tagged instincts emit `roles: [<persona-token>]` REPLACING default `[software-engineer, frontend-engineer]`. Mapping at `hooks/_lib/learn_persona_roles.py::_PERSONA_TO_ROLE` — lockstep update with agent frontmatter.
