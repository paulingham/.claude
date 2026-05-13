---
category: decision
---

**Tool surface for vlm-critic is pinned narrower than spec-blind-validator.**

vlm-critic ships `tools: [Read, Write]` with `disallowedTools: [Bash, Edit,
MultiEdit, Agent, Skill, Grep, Glob]` — 7 disallowed. spec-blind-validator
keeps `[Read, Write, Bash, Grep, Glob]` because it needs to discover the
public API surface via Grep and shell out to test runners via Bash.
vlm-critic operates on a closed file set named verbatim by index.json, so
no discovery and no shell side-effects are needed. The single Write target
is index.json under each route's `visual_regression` block.

The Tier 0 contract test asserts this exact 2-tool / 7-disallowed surface
with a fixed-string assertion (no "or equivalent" slop). Downstream
maintainers extending vlm-critic to add e.g. a screenshot-resize helper
MUST NOT silently widen the tool surface — the contract test will fail
and force a deliberate revision.

---
category: warning
---

**A2 mutant is documented as equivalent — exclude-pattern flip is not
killed by any direct test.** See `build-mutation-slice-b.md` § Documented
Equivalent Mutant (A2). The justification mirrors spec-blind's
CR-MED-4 belt-and-braces decision: the four `!.*/node_modules/.*` /
vendor / dist / build excludes are defense-in-depth, but no production
code path can produce a node_modules-rooted baseline png path (the
producer is design-qc Step 5.5 which writes deterministically to
`pipeline-state/{task-id}/visual-baselines/`). The realpath gate
(SEC-HIGH-1) is the load-bearing defense, not the exclude rule. If a
future code path emerges that DOES allow node_modules paths to reach the
allowlist matcher, a dedicated Tier 2 test should be added to kill A2.

---
category: decision
---

**Soak-end placeholder file was committed by slice-a, NOT slice-b.**
Per the slice-a scratchpad note + the existing
`pipeline-state/vlm-spec-blind-common-extract-soak-end/pipeline.md`,
slice-a created the placeholder to satisfy its own Tier 0 contract test
(`test_soak_end_placeholder_file_exists_with_correct_not_before_anchor`).
The plan § 10 row 9 said slice-b would commit it, but slice-a was
forced to commit it first to clean its batched-RED→GREEN cycle.

The existing placeholder body cites BOTH consolidation targets
(`hooks/_lib/vlm-critic-guard-common.sh` AND
`hooks/_lib/spec-blind-guard-common.sh`) and carries the correct
`not_before: 2026-06-09T00:00:00Z` frontmatter. Slice-b verified the
file's contract is satisfied without modification — no extra body
section was needed.

---
category: pattern
---

**Mutation runner location**: `tests/mutation/vlm_critic_guard_mutation_runner.sh`
mirrors slice-a's `tests/mutation/visual_diff_mutation_runner.sh` pattern.
Both are committed to the repo (not in `.claude-scratch-tools/`) because:
1. They are deterministic, reproducible test artifacts (the verify phase
   can re-run them as a Tier 3 mutation check independently of build).
2. The mutator functions document the "intended-killable" branches
   explicitly with rationale — they ARE the contract for which security
   branches must remain covered as the codebase evolves.

Slice-b uses sed-based mutators (slice-a used perl); both work. The sed
approach is slightly more portable on macOS BSD (where perl-i has flag
quirks). Future slices may pick either.

---
category: discovery
---

**Settings.json registration is additive within the existing
Read|Grep|Glob matcher block, NOT a new matcher entry.** The PreToolUse
schema allows multiple hooks under one matcher; the spec-blind hook and
the vlm-critic hook both register on `Read|Grep|Glob`. This preserves
the architect's "register alongside spec-blind" instruction without
introducing a duplicate matcher key.

---
category: fragility
---

**Tier 0 contract test regex parser bug in initial RED.** My first cut of
the disallowedTools assertion in `tests/contract/spec_vlm_critic_isolation.py`
used a regex `\s+-\s+\S+\n)+` which silently dropped the final list item
when the YAML block was followed immediately by `---` (no trailing blank
line between last list item and frontmatter close). The fix was to
replace the regex with a line-by-line parser
(`_yaml_list_under(frontmatter, key)`) that walks lines until a non-list
or top-level key. This is a generic YAML-list-extraction helper —
downstream slice-c tests should consider using the same pattern if they
need to assert YAML-list contents.
