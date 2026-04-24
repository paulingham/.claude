# Expected Outcomes (Oracle)

All assertions live in `hooks/tests/test-hooks.sh`. After applying a correct
candidate diff to `context/`, the suite must still pass AND the following new
assertions must be present and green.

## New test block: "per-project instincts bootstrap"

Seeded test environment:
- fake `$HOME`
- fixture git repo with a stable remote so `_project_hash --fallback "local"`
  returns a deterministic hash (call it `$PPI_HASH`)
- seeded `learning/$PPI_HASH/observations.jsonl` with 3 lines

### Required assertions

1. **First run exits 0** — invoking `session-start-bootstrap.sh` with the hermetic
   `HOME` returns status 0.
2. **Instincts dir created** — `learning/$PPI_HASH/instincts/` exists after the
   first run.
3. **LEARN HINT emitted with count** — stdout contains a line matching
   `LEARN HINT: 3 observations without instincts` (observation count 3).
4. **Idempotent** — a second invocation also exits 0 with the directory already
   present.
5. **LEARN HINT emitted at most once per run** — `grep -c "LEARN HINT:"` on the
   output of a single invocation returns exactly `1`.
6. **LEARN HINT suppressed when any instinct exists** — after writing a single
   `.md` file with a `confidence:` line into the per-project instincts dir, the
   next invocation's stdout must not contain `LEARN HINT:`.
7. **LEARN HINT suppressed under threshold** — with fewer than 3 observation
   lines, the invocation's stdout must not contain `LEARN HINT:`.
8. **`/learn` SKILL.md contains the idempotent mkdir** — `grep` over
   `skills/learn/SKILL.md` finds a literal
   `mkdir -p "$HOME/.claude/learning/$PROJECT_HASH/instincts"` line.

### Regression guard

The existing test suite (`hooks/tests/test-hooks.sh`, excluding the new block)
continues to pass. Total passing count must rise by exactly the number of new
assertions added (+8 over the pre-change baseline).

## Qualitative outcome

`LEARN HINT: <N> observations without instincts — invoke /learn` is the line
shape observed in the live harness once observations have accumulated against an
empty per-project instincts dir.
