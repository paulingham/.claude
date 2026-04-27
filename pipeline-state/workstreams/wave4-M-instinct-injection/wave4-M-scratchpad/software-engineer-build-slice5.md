---
category: decision
---

The prompt's Section C item 3 says "Test that each declared category is one of the allowed enum values: `discovery|warning|pattern|fragility|decision`". This conflicts with the actual implementation: the `instinct_categories:` field on `agents/*.md` files holds **role-name tokens** (per the Slice 4 mapping in `wave4-M-plan.md` lines 388-403 — `software-engineer`, `frontend-engineer`, etc.), NOT the `discovery|warning|pattern|fragility|decision` enum. That enum belongs to a NEW `category:` field on **instinct files** (per prompt Section B item 5), which is the scratchpad-finding-category provenance for scratchpad → instinct promotion.

I wrote the test to validate the actual contract: `instinct_categories:` is a non-empty YAML list of role-name strings, the loader returns a list for every shipped role, and unknown roles return None. This is the regression that matters — it locks the Slice 4 contract that was the load-bearing fix in this wave (lists must round-trip as Python lists, not corrupt to strings via the broken `pipeline_frontmatter` parser).

Reviewers: if you wanted the enum check to also assert agent files declare a `category:` field of `discovery|warning|pattern|fragility|decision`, that's a different field on different files and would need its own test. Happy to add it if the reviewer disagrees with my reading.

---
category: pattern
---

The Slice 4 loader (`agent_instinct_categories_loader.py`) reads from `Path.home() / ".claude" / "agents"` by default — which resolved to the GLOBAL `~/.claude/agents/` directory during pytest, NOT the worktree's `agents/` dir. The Slice 4 frontmatter additions are only on the worktree's branch (not yet merged to main), so the loader returned None for every role. Fix: wrap every `load_agent_instinct_categories(...)` call in `patch.dict("os.environ", {"CLAUDE_AGENTS_DIR": str(AGENTS_DIR)})`. This pattern is consistent with `tests/test_agent_instinct_categories_loader.py` (Slice 4) and `tests/test_instinct_hook.py` (Slice 3 — the same env-var approach so subprocess HOME stays intact for `yaml` import).

---
category: discovery
---

Final test count: +6 new tests, 825 total passing (up from 819 baseline pre-slice). Pre-existing failures `test_install_tools.py::test_shellcheck_clean_if_available` and `test_settings_portability.py::SettingsPortabilityBatsSuite::test_bats_suite_passes` remain unchanged — confirmed not slice-5 regressions (verified on both `wave4-M-instinct-injection` head 0b429ae and `build/wave4-M-slice5`). The third claimed pre-existing failure (`new-session bats`) was not observed in this run; only the two listed above appear.

---
category: warning
---

The `/learn` SKILL.md update added an `applies_to_roles:` field as a "forward-looking alias" for `roles:`. This is documented as IGNORED by the current loader — `roles:` remains the load-bearing field. If a future contributor expects the loader to read `applies_to_roles:`, they'll be surprised. The doc note is explicit that "Future loader versions may merge the two", but the loader does not currently. I added this field per the prompt's Section B item 5 ("`applies_to_roles:` is a YAML list (e.g., `[software-engineer, frontend-engineer]`)"), but kept it as a no-op alias to avoid changing Slice 1/2 loader behavior in Slice 5 (which is doc-only for code).

---
category: decision
---

The orchestrator/agent-orchestration.md `### Instinct Injection (Automatic)` section was rewritten in place rather than appended-to. Rationale: the existing section was aspirational and conflicted with the new Path-B reality. Leaving it would have created two truth sources. The new heading is `### Instinct Injection (every Agent spawn)` (matching the verb form the plan used at line 338 of `wave4-M-plan.md`). The renamed section title is intentional — it signals to grep that the contract changed.

---
category: pattern
---

Doc-edit cycles for Slice 5 used straight Edit tool calls (no TDD because no code change). The single TDD cycle was for `tests/test_learn_roles_enforcement.py` — RED came from the loader returning None against the wrong agents dir; GREEN came from the env-var fix; REFACTOR was extracting `_load(role)` helper to dedupe the `patch.dict` boilerplate across the loader-touching test classes.
