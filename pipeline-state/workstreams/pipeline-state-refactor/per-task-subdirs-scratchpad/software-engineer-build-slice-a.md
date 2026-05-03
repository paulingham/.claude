---
category: decision
---

Split `pipeline_state_paths.py` into three Python files (public API +
`_helpers` + `_precedence`) and added a `_cli` bridge for the bash
helpers. The 50-line file cap from `code-shape-check.sh` could not
hold all of: discovery globs (4 quadrants), task-id derivation,
workstream identity, and the workstream-beats-root-then-mtime
precedence rule in one module. The split is by axis-of-change:
discovery globs change when layouts change, precedence changes when
collision rules change, public API changes never. Slice B+C consumers
import from `pipeline_state_paths` only — the split is invisible to
them.

---
category: pattern
---

Bash 3.2 cannot do mtime-aware multi-glob precedence cleanly without
process substitution or `mapfile`. The bash helper
(`pipeline-state-paths.sh`) delegates `_psp_find_active_pipelines` and
`_psp_discover_state_path` to a tiny Python CLI shim
(`pipeline_state_paths_cli.py`) instead. This keeps each
`_psp_*` function ≤5 lines and avoids re-implementing the precedence
logic in two languages. Future bash hooks (Slice B) should follow this
pattern when they need pipeline-state path resolution.

---
category: warning
---

`code-shape-check.sh` enforces the 50-line file cap on every Write.
The orchestrator/agent-orchestration.md and orchestrator/pipeline-orchestration.md
files are NOT subject to the cap (they are docs, not code) — but any
new Python helper added by Slice B/C MUST stay under 50 lines or be
split immediately. Anticipate splits when designing helpers; don't
write 80-line files and hope.

---
category: discovery
---

Pytest in this repo runs via `rtk proxy python3 -m pytest` — the
default `pytest` invocation is intercepted by the rtk hook with a
"Failed to spawn process" error. The canonical command from session
memory ("PYTHONPATH=hooks/_lib python3 -m pytest …") works only
through `rtk proxy`. Slice E.5 / E test runners need this same
invocation. The bats runner (`bats tests/shell/...`) does not need
proxying.

---
category: decision
---

The 11-stub batched RED ran cleanly: 8 tests RED via
`ModuleNotFoundError` (helper missing), 2 tests RED via
substring-not-in-doc, 1 bats test RED via exit 127 (file missing).
All RED for the right reason — none broken on syntax or wrong import
path. The audit artifact is split across `*-build-red-py.txt` (62
lines) + `*-build-red-bats.txt` (9 lines) + the human-readable
summary `*-build-red.txt`.

---
category: decision
---

Mutation gate at 79.2% (19/24 mutants killed). Five surviving mutants
cluster around three thin behavioural seams: tie-mtime semantics
(M21/M22/M24), `discover_state_path` symmetric existence (M23), and
the health-reports surface (M9). All three seams are explicitly
covered by Slice E / Slice D stubs per the plan — Slice A locks the
contract; downstream slices lock the runtime. Survivor disclosure is
in `*-build-mutation.md`.
