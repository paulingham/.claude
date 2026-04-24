# Bootstrap per-project instincts directory + emit /learn nudge

## Problem

Agents spawned by the pipeline are supposed to receive a "Learned Patterns" block
compiled from the harness's learning system. In practice, that block is coming
through empty for this project even though observations have been accumulating in
`learning/{project-hash}/observations.jsonl` for a while.

The session-start bootstrap hook currently reads instincts from a single global
path (`learning/instincts/`). Nothing creates per-project instinct directories,
and there is no signal that encourages the operator to run `/learn` when
observations have piled up without ever being consolidated.

The fix should:

1. Bootstrap per-project instinct storage so `/learn` has a home to write into,
   without breaking the existing global instincts (they should still surface until
   per-project ones exist).
2. Nudge the operator to invoke `/learn` when there is enough raw data to justify
   it.
3. Be idempotent — running the hook twice in a session must not double-emit the
   nudge.

## Acceptance Criteria

- The session-start bootstrap hook ensures a per-project instincts directory
  exists at `learning/{project-hash}/instincts/` on every run. `mkdir -p` style —
  silent when already present, creates it when not.
- The hook's "Learned Patterns" list prefers per-project instincts when any exist
  and falls back to the existing global location only when the per-project
  directory is empty. Behaviour when both are empty is unchanged (no section
  printed).
- The hook emits a single `LEARN HINT:` line naming the current observation count
  when **both** of these are true:
  - `learning/{project-hash}/observations.jsonl` has ≥ 3 lines
  - The per-project instincts directory contains zero `.md` files
- The `LEARN HINT:` line is suppressed when any per-project instinct `.md` exists,
  and suppressed when observations are under the threshold.
- The `LEARN HINT:` line appears at most once per hook invocation (no
  duplication).
- The `/learn` skill performs the same idempotent directory bootstrap at the top
  of its process, so `/learn` succeeds on its very first invocation in a project
  — before any instinct has been written.
- Tests for the above are hermetic: they use a fake `$HOME`, a fixture git repo
  with a stable remote so the project hash is deterministic, and clean their own
  temp state up afterwards.
- Existing hook test suite continues to pass.

## Out of Scope

- Migrating existing global instincts into per-project directories.
- Changing the `/learn` scoring or promotion rules themselves.
- Anything about the orchestrator's instinct-injection prompt composition.
