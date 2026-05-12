---
category: discovery
---

`rules/_detail/*` was renamed to `protocols/*` at commit d19bb59 (before Story 2 was planned).
The Story-2 plan referenced `rules/_detail/pipeline-protocol.md` but the actual file is now
`protocols/pipeline-protocol.md`. The `rules/<topic>.md` stub files still resolve back-compat;
new references must use `protocols/`.

---
category: fragility
---

The `_step_5b_body` helper in `tests/_step_5b_helpers.py` slices Step 5b by treating
ANY `## ` heading as the terminator, INCLUDING headings inside fenced code blocks. My
first implementation embedded `## Sandbox Verify` inside a `\`\`\`markdown` code block
in Step 5b body — the helper truncated the body early at that line, causing 4 tests to
fail. Fix: move the `## Sandbox Verify` template OUT of Step 5b body into its own
`### Sandbox Verify Section` subsection under Phase Output. Future authors editing
`tests/_step_5b_helpers.py` must NOT embed `## ` headings inside code blocks within
Step 5b prose, or document a code-block-aware variant.

---
category: pattern
---

The Story 2 catalog-row lockstep test (`SandboxSkippedReasonsLockstepWithSkillBody`) walks
the Story-2 reasons (`no-testable-changes`, `env-hatch`) inline rather than parsing both
sources for a generic set-equality check. This is intentional: Story 3 will add new reasons
to the catalog (e.g. `e2b-provision-failed`) BEFORE updating Step 5b body in the same PR.
The lockstep enforces "every catalog reason also in skill body" only for the named tokens
to avoid a chicken-and-egg failure when Story 3's first-test commit lands. Generic
set-equality lockstep can be added in Story 3 once both sides have been extended together.

---
category: decision
---

Chose to extract the `## Sandbox Verify` template into a sibling subsection `### Sandbox Verify Section`
under `## Phase Output` (alongside `### Decision Record` and `### Context for Next Phase`) rather than
inlining it inside Step 5b. **Why**: Step 5b's responsibility is the procedure (when, how, branches);
the template's responsibility is the state-file format. The two are separable. **Watch**: if Story 4 adds
more SANDBOX_*-specific output fields, they belong in the template subsection, not the Step 5b body.
The `### Context for Next Phase` subsection already documents `## Context for Review` the same way —
new pattern is consistent with existing precedent.

---
category: warning
---

`tests/conftest.py` ONLY prepends `hooks/_lib` to sys.path — it does NOT add `tests/` itself.
Three test files import `_step_5b_helpers` from the same `tests/` dir; each prepends
`tests/` to sys.path with a per-file `sys.path.insert`. This is intentional: the conftest
seam is for production-code helpers under `hooks/_lib`, not for test-only helpers. Story 3
and later authors adding shared test-helper modules under `tests/` should follow the same
per-file `sys.path.insert(0, str(Path(__file__).resolve().parent))` pattern, not extend
the conftest. If Story 4 needs a third type of helper, consider a `tests/_helpers/` package
with `__init__.py` so Python treats it as a normal package.
