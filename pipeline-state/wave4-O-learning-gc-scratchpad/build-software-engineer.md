---
category: discovery
---

The 50-line file shape limit forces decomposition for archive logic: kept
`learning_gc_archive.py` as a thin orchestrator (26 lines) and split parse /
gzip-append / atomic-rewrite helpers into `learning_gc_archive_io.py` (46
lines). Both modules ship dedicated test files (`test_learning_gc_archive.py`,
`test_learning_gc_archive_io.py`) — the TDD guard requires per-module test
files at `tests/test_<basename>.py`.

---
category: pattern
---

Atomic write + gzip append pattern works cleanly with stdlib: `tempfile.mkstemp`
in the same parent directory + `os.replace` for the obs.jsonl rewrite, and
`gzip.open(..., "at")` for monthly archive appends (gzip handles concatenation
of compressed streams transparently — appending to an existing `.gz` produces
a valid file readable as a single stream).

---
category: warning
---

`subprocess.run(timeout=N)` raises `subprocess.TimeoutExpired` rather than
returning — narrow-catching it (instinct 0.5) is mandatory in
`learning_gc_vacuum.vacuum_db`. A bare `except Exception` would mask unrelated
bugs and was rejected.

---
category: decision
---

Chose `python3 runner.py` invocation from the bash hook over inlining all
logic in bash. Reason: gzip + JSON parsing + atomic file writes are far
cleaner in Python stdlib than bash. The bash hook is intentionally tiny
(24 lines) — it only resolves the project hash via `_project_hash` and
shells to `learning_gc_runner.py`, which orchestrates `is_gc_due`,
`archive_observations`, `vacuum_db`, `update_state`. The runner swallows
all exceptions to honour the "never block session start" iron law.
