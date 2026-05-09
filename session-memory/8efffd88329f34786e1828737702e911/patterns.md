# Patterns & Conventions
_Code patterns in use (service objects, barrel exports, hook composition). Naming conventions. Architecture decisions observed. Framework-specific idioms. Session discoveries: gotchas encountered, surprising behavior, solutions to problems. Agent effectiveness: what approaches worked well, what wasted time._

## Test helpers
- `tests/test_learn_anti_pattern_mining.py` exposes module-scope helpers `_make_pipeline_obs(pipeline_id, rounds, scratchpad_findings)`, `_write_observations(tmp_path, records)`, `_emitted(tmp_path)` — importable; extend `_make_pipeline_obs` with new optional kwargs (e.g. `patch_critic_rounds`, `persona_rejections`) rather than forking.
- `tests/test_build_step_*` use `Path(__file__).resolve().parents[1] / "skills" / ...` + the `_step_1d_body(body)` helper from `test_build_step_1d_env_hatch.py` for "find a section by `### Step` heading and return its body up to the next `### Step`" — parameterise to other Step headings.

## Doc-regression assertion idiom
- For tests asserting multiple tokens appear in the SAME contiguous paragraph of a skill `.md`, use a non-greedy bounded regex like `r"<token1>[\s\S]{0,400}?<token2>[\s\S]{0,400}?<token3>"`. The `[\s\S]{0,400}?` cap prevents matching across unrelated paragraphs that share a token (e.g. discriminating a new refactor paragraph from an existing PBT-overlap paragraph that contains `cap=3` literally but lacks the env-var token).

## Code-shape pressure → sibling extraction
- When a `hooks/_lib/<module>.py` projects to cross the 300-line shape cap (`rules/_detail/engineering-invariants.md` § Code Shape), extract a cohesion-driven sibling module (e.g. `learn_anti_pattern_mining.py` → `learn_persona_roles.py`). Parent re-exports the sibling's public surface via `from learn_persona_roles import ...` with `# noqa: F401` for backward-compat with consumers that import from the parent.

## Persona-categorical role tokens (instinct injection)
- `agents/patch-critic.md::instinct_categories` declares `[patch-critic, patch-critic-correctness, patch-critic-regression, patch-critic-scope, code-reviewer]`. Persona-tagged instincts emit `roles: [<persona-categorical-token>]` REPLACING (not unioning with) the default `[software-engineer, frontend-engineer]` so the instinct lands at patch-critic spawns only.
- Canonical persona→role mapping lives at `hooks/_lib/learn_persona_roles.py::_PERSONA_TO_ROLE`. New personas require lockstep updates: the constant + `agents/patch-critic.md::instinct_categories`. Tier 0 mapping test catches drift in the constant; agent-frontmatter snapshot test catches drift in the agent file.
