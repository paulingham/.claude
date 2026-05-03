# Slice E.5 — Mutation Report (helper code)

## Method

Manual enumeration of plausible mutations on the helper code lines, with
mapping to the test that would catch each one. Two helper files in scope:

- `tests/_fixtures/pipeline_state.py` (`make_pipeline_fixture`,
  `_validate_layout`)
- `tests/_fixtures/_pipeline_state_builders.py` (`build_phase_path`,
  `write_state_file`, `_ws_root`)
- `tests/_fixtures/pipeline_state.sh` (`_psf_phase_path`,
  `_psf_write_state`, `_psf_validate`, `_psf_parse_one`, `_psf_emit`,
  `_psf_make_fixture`)

Test files: `tests/_fixtures/test_pipeline_state_fixtures.py` (15) +
`tests/shell/test_pipeline_state_fixtures_sh.bats` (11). Both green.

## Python mutations

| # | Source | Mutation | Killed by |
|---|---|---|---|
| 1 | `pipeline_state.py:32` `if phases else list(DEFAULT_PHASES)` | drop `else` branch | `test_default_phase_is_pipeline_only` |
| 2 | `pipeline_state.py:34` `for phase in selected:` | replace `selected` with `[]` | `test_legacy_layout_writes_flat_pipeline_md` (file would not exist) |
| 3 | `pipeline_state.py:37` `if phase == "pipeline"` | flip to `!=` | `test_legacy_layout_writes_flat_pipeline_md` (returns wrong path) |
| 4 | `pipeline_state.py:39` `pipeline_path or build_phase_path(...)` | drop `or` fallback | `test_returns_pipeline_md_path_when_phase_omitted_from_phases` |
| 5 | `pipeline_state.py:44` `not in ("new", "legacy")` | swap to `in` | `test_invalid_layout_raises_valueerror` |
| 6 | `_pipeline_state_builders.py:13` `if layout == "new"` | flip to `!=` | `test_legacy_layout_writes_flat_pipeline_md` + `test_new_layout_writes_subdir_pipeline_md` |
| 7 | `_pipeline_state_builders.py:14` `task_id / f"{phase}.md"` | swap to `task_id-{phase}.md` | `test_new_layout_writes_subdir_pipeline_md` (path mismatch) |
| 8 | `_pipeline_state_builders.py:15` `f"{task_id}-{phase}.md"` | swap to `f"{task_id}/{phase}.md"` | `test_legacy_layout_writes_flat_pipeline_md` |
| 9 | `_pipeline_state_builders.py:21` `parents=True` | drop | `test_legacy_layout_with_workstream` (parent dir absent → write fails) |
| 10 | `_pipeline_state_builders.py:21` `exist_ok=True` | drop | `test_idempotent_overwrite` (second call raises) |
| 11 | `_pipeline_state_builders.py:24-26` frontmatter fields | replace `task_id` with literal | `test_phase_field_is_per_phase` + frontmatter content checks |
| 12 | `_pipeline_state_builders.py:33` `if workstream:` | flip to `if not workstream:` | `test_workstream_empty_string_means_root` + `test_legacy_layout_with_workstream` |
| 13 | `_pipeline_state_builders.py:34` `"workstreams" / workstream` | swap to plain `workstream` | `test_legacy_layout_with_workstream` |

13 mutations, all killed.

## Bash mutations

| # | Source | Mutation | Killed by |
|---|---|---|---|
| 14 | `pipeline_state.sh:19` `[ -n "$ws" ]` | flip to `[ -z "$ws" ]` | `layout=new + workstream nests under workstreams/{ws}/{task}/{phase}.md` |
| 15 | `pipeline_state.sh:20` `[ "$layout" = "new" ]` | flip to `!=` | `layout=legacy writes flat pipeline.md and echoes its path` |
| 16 | `pipeline_state.sh:20` printf format `%s/%s/%s.md` | swap to `%s-%s-%s.md` | `default layout=new writes subdir pipeline.md` |
| 17 | `pipeline_state.sh:21` printf format `%s/%s-%s.md` | swap to `%s/%s/%s.md` | `layout=legacy writes flat pipeline.md` |
| 18 | `pipeline_state.sh:26` `mkdir -p` | drop `-p` | `layout=new + workstream` (deep dir) |
| 19 | `pipeline_state.sh:32-33` validation `[ -z "$1" ]` | flip to `[ -n "$1" ]` | `missing --task-id returns 1` |
| 20 | `pipeline_state.sh:34` `case "$3" in new\|legacy)` | drop `legacy` | `layout=legacy` family of tests |
| 21 | `pipeline_state.sh:40-44` arg parser | swap `_PSF_TASK` and `_PSF_LAYOUT` assignment | `default layout=new` (would assign task to layout) |
| 22 | `pipeline_state.sh:45` positional fallback | drop | `missing STATE_DIR returns 1` would still pass; but `default layout=new` would fail since `_PSF_DIR` would stay empty |
| 23 | `pipeline_state.sh:55` `[ "$phase" = "pipeline" ]` | flip to `!=` | `default layout=new` returns wrong path |
| 24 | `pipeline_state.sh:57` `[ -z "$pipeline_path" ]` fallback | drop | `phases='build' (no pipeline) still echoes pipeline.md path` |
| 25 | `pipeline_state.sh:64` while-loop body | swap order to validate before parse | tests would fail because validation runs against unparsed args (all empty) |

All 13 of 13 bash mutations killed.

## Kill rate

- Python: 13/13 = 100%
- Bash: 13/13 = 100%
- Combined: **26/26 = 100%** (well above the ≥70% threshold)

## Surviving mutation list

None.
