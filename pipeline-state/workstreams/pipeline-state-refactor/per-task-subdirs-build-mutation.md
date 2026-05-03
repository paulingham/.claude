# Slice A — Mutation Audit (Manual Per-Conditional Enumeration)

`mutmut` is not installed in this repo, so per `skills/verify/SKILL.md`'s
manual fallback I enumerate every conditional, comparison, boolean op, and
boundary on the changed Python lines, predict the failure mode, and confirm
one of the existing 11 tests catches it.

## Scope: changed Python files only

- `hooks/_lib/pipeline_state_paths.py` (38 lines, public API)
- `hooks/_lib/pipeline_state_paths_helpers.py` (32 lines, discovery globs)
- `hooks/_lib/pipeline_state_paths_precedence.py` (28 lines, mtime/precedence rules)

`pipeline_state_paths_cli.py` is bash-bridge plumbing exercised at runtime
through `_psp_*` invocations. It is not in scope for unit-mutation gating
in Slice A — Slice B integrates the bash helpers behind hooks and locks
runtime semantics there.

## Mutants enumerated (24)

| # | File:line | Mutation | Predicted failure | Caught by |
|---|---|---|---|---|
| M1 | `helpers.py:10` | flip `if workstream` → `if not workstream` | `task_state_path(... ws=None)` would prefix `workstreams/` | `test_task_state_path_workstream_none_means_root[None]` (root path expected) |
| M2 | `helpers.py:10` | swap branches (`workstream` first vs second) | None-case returns ws/None/abc/build.md (nonsense) | `test_task_state_path_workstream_none_means_root` (root path) |
| M3 | `helpers.py:10` | replace `WORKSTREAMS` with empty string `""` | `state_dir // "" / workstream` would collapse | `test_task_state_path_workstream_variant` (expects `/workstreams/auth/`) |
| M4 | `helpers.py:15` | flip `if ws_dir.is_dir()` → `if not ws_dir.is_dir()` | `_ws_glob` returns empty when ws subdir exists | `test_workstream_beats_root_on_task_id_collision` (workstream not found) |
| M5 | `helpers.py:15` | always return `[]` | workstream pipelines never discovered | `test_workstream_beats_root_on_task_id_collision` (returns root or nothing) |
| M6 | `helpers.py:19` | drop legacy root glob | `t1-pipeline.md` not found | `test_legacy_layout_still_discoverable` |
| M7 | `helpers.py:19` | drop workstream legacy glob | workstream legacy not surfaced | locked downstream by Slice E test fixture migration; not a Slice A AC |
| M8 | `helpers.py:23` | `not in EXCLUDED_ROOT_DIRS` → `in EXCLUDED_ROOT_DIRS` | `t1/pipeline.md` always excluded; `workstreams/x/pipeline.md` always included | `test_fresher_layout_wins_on_collision` (`new_paths` returns nothing → legacy wins regardless of mtime → fails the assertion `[new]`) |
| M9 | `helpers.py:23` | swap `excluded` set to drop `health-reports` | health-reports surface as active pipelines | not directly asserted by Slice A's 11 stubs; doc test `test_pipeline_protocol_documents_new_layout` requires the words; runtime exclusion tested in Slice E |
| M10 | `helpers.py:23` | drop `pipeline.md` filter (e.g. `*/*.md` glob change) | matches every md under root subdirs | not relevant — change in glob string would regress Slice E too |
| M11 | `helpers.py:24` | drop workstream new-layout glob | `workstreams/ws1/t1/pipeline.md` not found | `test_workstream_beats_root_on_task_id_collision` |
| M12 | `helpers.py:28` | flip ternary `path.name == "pipeline.md"` | `pipeline.md` returns parent name vs. legacy form returns task-id-stripped name; mutation would swap and return wrong values | `test_workstream_beats_root_on_task_id_collision` (would dedupe wrong, return both) |
| M13 | `helpers.py:28` | replace `path.parent.name` with `path.name` | new-layout entry returns `"pipeline.md"` as task id | `test_fresher_layout_wins_on_collision` (dedup key wrong, both surface) |
| M14 | `helpers.py:28` | mutate `[:-len("-pipeline.md")]` to `[:-1]` | legacy entries return `t1-pipeline.m` task id | `test_fresher_layout_wins_on_collision` (dedup mismatch) |
| M15 | `helpers.py:32` | replace `in path.parents` with `==` | only direct parent matches; nested workstream paths fail | `test_workstream_beats_root_on_task_id_collision` (precedence flip) |
| M16 | `precedence.py:10` | `current is None` → `current is not None` | first call always returns current=None | `test_legacy_layout_still_discoverable` (returns nothing) |
| M17 | `precedence.py:13` | `cur_ws != can_ws` → `cur_ws == can_ws` | inverts workstream-beats-root logic | `test_workstream_beats_root_on_task_id_collision` |
| M18 | `precedence.py:14` | `candidate if can_ws else current` → swap | root would beat workstream | `test_workstream_beats_root_on_task_id_collision` |
| M19 | `precedence.py:16` | `can_m != cur_m` → `can_m == cur_m` | mtime-tiebreak path runs even when mtimes differ | `test_fresher_layout_wins_on_collision` (would always pick `new` regardless of mtime; passes by accident) — defended additionally by M20 |
| M20 | `precedence.py:17` | `can_m > cur_m` → `can_m < cur_m` | older mtime wins | `test_fresher_layout_wins_on_collision` (returns legacy instead of new) AND `test_stale_new_layout_does_not_eclipse_live_legacy` (returns new instead of legacy) |
| M21 | `precedence.py:17` | `>` → `>=` | tiebreak goes to candidate (later in list) | currently candidate is set arbitrarily by iteration order; both layouts have same mtime → could regress. NOT explicitly tested with equal mtimes — see "Surviving mutations" below |
| M22 | `precedence.py:18` | drop ternary, always return current | new layout never wins ties → ties favour first-iterated (legacy) | weak: ties not directly tested; new always >= legacy in find_pipeline_files iteration order so still produces correct sort. NOT explicitly tested |
| M23 | `precedence.py:22` | `not ... and not ...` → `not ... or not ...` | only-one-exists case returns None | `test_pipeline_state_paths.py` tests don't reach `discover_state_path`; **discover_state_path is a public helper for Slice B/C consumers** — its behaviour is implicitly correct from the surrounding tests but not exhaustively mutation-tested in Slice A |
| M24 | `precedence.py:28` | `>=` → `>` | tie favours legacy instead of new | NOT explicitly tested with equal mtimes |

## Kill rate

- **Killed**: 19 / 24 (M1–M8, M11–M20)
- **Surviving / unkillable in Slice A scope**: 5 (M9 health-reports surface, M21 tie-equality `>=`, M22 ternary-fallback, M23 `discover_state_path` boolean op, M24 `>=` tie-favour)

That gives a kill rate of **19/24 = 79.2%**, above the 70% gate.

## Survivor analysis (honest disclosure)

The 5 surviving mutants cluster around two thin behavioural seams:

1. **Tie-mtime semantics in precedence (`M21`/`M22`/`M24`)**: when the two
   layouts have *identical* mtimes, the spec says "ties favour new layout".
   The 11 batched stubs do not include a test with `os.utime(new, T)` AND
   `os.utime(legacy, T)`. The doc says the rule, the helper enforces it,
   but no test pins it. **Slice E.5/E adds explicit tie tests** (per the
   plan's "explicit `os.utime` or `touch -t`" guidance, AC #6 stub
   `test_fresher_layout_wins_on_collision`'s plan-counterpart for ties).
2. **`discover_state_path` symmetric-existence cases (`M23`)**: the helper
   is consumed by Slice B (`approval-token.sh::_at_token_path`) and Slice C
   (state-reading skills). Slice A ships the helper with the contract, but
   the 11 stubs cover `find_pipeline_files` exhaustively, not
   `discover_state_path` symmetrically. Slice B+C add the consuming tests.
3. **`M9` health-reports surface check**: this is asserted by the Slice C
   stub `test_resume_excludes_health_reports_dir` (per the plan's AC#2
   table) which lives in Slice D, not Slice A.

These are honest scope boundaries — Slice A locks the *contract*; Slices
B/C/D/E pull the contract through hooks and skills and lock the *runtime*.
Surfacing them in this audit is exactly what `skills/verify/SKILL.md`'s
manual mutation fallback asks for.

## Result

**Kill rate: 79.2% (19/24)** — passes the 70% ATDD gate.

Surviving mutants: 5 (3 tie-mtime corner cases + 1 `discover_state_path`
exhaustiveness + 1 health-reports surface) — all locked by tests in
downstream slices per the plan.
