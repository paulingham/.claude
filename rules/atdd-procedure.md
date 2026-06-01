# ATDD Procedure

This file is a stub. Content has moved to:

- `protocols/atdd-procedure.md` — full ATDD cycle (batched RED, mutation gate, audit trail, per-behaviour TDD exceptions). Loaded by `/harness:build-implementation` and `/harness:bug-fix` only; not auto-loaded.

The ATDD iron law (no AC ships without a failing-then-passing test + ≥70% mutation score) lives in `rules/core.md`. Engineering invariants (code shape, naming, testing standards, security baseline) live in `protocols/engineering-invariants.md`.

Existing references to `rules/atdd-procedure.md` continue to resolve here. New
references should point to `protocols/atdd-procedure.md`.
