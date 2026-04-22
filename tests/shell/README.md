# Shell test harness

This directory holds `bats-core` specs that exercise the harness's bash
surfaces (hooks, install scripts, project-hash helpers). The tests live
alongside the Python suite but run under a different runner.

## Prerequisites

- `bats-core` (installed by `scripts/install-tools.sh` — Slice 3).
- macOS stock `bash` 3.2 is sufficient for the wrapper; individual specs
  may require bash 4+ if they rely on `mapfile`, associative arrays, etc.

## Running

```sh
# Local dev: skips cleanly when bats is not installed yet.
bash tests/shell/run.sh

# CI: turns the skip into a hard failure so missing prerequisites are loud.
bash tests/shell/run.sh --require-bats
```

`run.sh` discovers every `*.bats` file under `tests/shell/` (recursive)
and invokes `bats` on the collected set. Specs may `load '../helpers.bash'`
to pick up `cli_assert_ok` and `cli_assert_stdout_match`.

## Files

- `run.sh` — the wrapper (bats-absent → SKIP; bats-present → run).
- `helpers.bash` — source-once helpers shared across every spec.
- `.bats-root` — marker file for relative `load` resolution.
- `smoke.bats` — placeholder spec proving the harness round-trips.
- Slice-specific specs (e.g. `project-hash.bats`, `settings.bats`) land here
  as later slices merge.

## Meta-tests

The wrapper itself is tested from Python (`tests/test_shell_harness.py`) so
the test suite stays green even on machines without bats. The Python tests
subprocess-invoke `run.sh` with a controlled `PATH` — one path without bats
(exercises the SKIP branch) and one with a stubbed `bats` (exercises the
invoke branch).
