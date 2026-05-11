---
id: spec-blind-validator-seed
confidence: 0.5
roles:
  - spec-blind-validator
  - qa-engineer
domain: testing
---

## Pattern

Three operating principles for the spec-blind validator (seed at confidence 0.5; refined as observation data accrues):

1. **The interface file IS the API.** When the AC literal disagrees with what an interface file declares, the interface is the contract; the AC is your hint about behaviour, the interface tells you the shape. Author tests against the declared types/methods, not against assumed shapes.
2. **A blocked Read is a design signal.** If `hooks/spec-blind-read-guard.sh` exits 2 on a Read attempt, that path is implementation, not contract. Find a public-surface alternative (`interface.{ext}`, `index.*`, `__init__.py`, OpenAPI/Protobuf/JSON-Schema). Do NOT escalate or work around — the block is doing its job.
3. **Three consecutive `SPEC_BLIND_INSUFFICIENT_SURFACE` on the same project means add `.claude/spec-blind.yml` opt-in.** This is the V2 trigger. Don't expand the convention-allowlist for one project's quirks; if a project has no public-surface convention, it should opt in explicitly.

## Why

The validator's value depends entirely on staying spec-blind. Working around the constraints (peeking at `src/`, importing internals "just for the test", expanding the allowlist for one project) collapses the role into "another build-time test author" — exactly the SWE-Bench-Pro failure mode the role was created to catch. Each principle preserves the independence property:

- Principle 1 stops the validator from second-guessing the interface declaration based on implementation memory.
- Principle 2 prevents creative bypass attempts (`cat`, `node -e`, etc.) — the hook IS the policy.
- Principle 3 prevents the convention-allowlist from drifting into a per-project config soup.

## How to Apply

- When you receive an AC, read it alongside the discovered `interface.{ext}` for the affected module. If the AC mentions a method/field not in the interface, emit `SPEC_BLIND_FAILED` with reason `ac-mentions-undeclared-surface` rather than guessing.
- When a Read or Bash attempt returns exit 2 with a `spec-blind-violations.jsonl` log line, do NOT retry with a different shape. Re-scope to the public surface. If you cannot, emit `SPEC_BLIND_INSUFFICIENT_SURFACE`.
- When the project repo has no discoverable public surface, emit `SPEC_BLIND_INSUFFICIENT_SURFACE` with reason `no-public-surface-discoverable`. After three such verdicts on the same project, `/learn` will recommend adding a `.claude/spec-blind.yml` opt-in. That is the V2 surface — defer to it.

## When NOT to Apply

- Bug-fix pipelines that touch a single module with a clear public interface — the convention-allowlist is sufficient; no opt-in needed.
- Harness-internal pipelines (`is_harness_internal_cwd` returns 0) — the recursion guard fires before any of these principles apply; `SPEC_BLIND_INSUFFICIENT_SURFACE` is emitted with reason `harness-internal-recursion`.

## Source

Seed instinct authored alongside `agents/spec-blind-validator.md` and `skills/spec-blind-validate/SKILL.md` at confidence 0.5. Refined as observation data accrues — recurring `SPEC_BLIND_FAILED` patterns will lift confidence; recurring `SPEC_BLIND_INSUFFICIENT_SURFACE` will trigger the V2 opt-in recommendation.
