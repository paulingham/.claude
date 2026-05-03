---
category: discovery
---

Slice E scope verification (post-integration audit on tip a9937bf):

The 4 AC #8 stubs are the COMPLETE Slice E scope. Audit findings:

- The 11 "missing" files Slice E.5 reported are redundant — Slice B
  authored more-specific equivalents (`*_dual_path.*`, `*_new_layout.*`)
  that already cover the underlying production hooks/skills:

| Plan-named (missing) | Slice B replacement |
|---|---|
| `test_pipeline_state_guard.py` | `test_pipeline_state_guard_dual_path.sh` (AC #4) |
| `test_auto_learn_gate.py` | `test_auto_learn_gate_dual_path.py` (AC #4) |
| `test_pipeline_analytics.sh` | `test_pipeline_analytics_dual_path.sh` (AC #4) |
| `test_observation_capture.sh` | `test_observation_capture_dual_path.sh` (AC #4) |
| `test_subagent_stop_trajectory.sh` | `test_subagent_stop_trajectory_dual_path.sh` (AC #4) |
| `test_pipeline_resume.py` | `test_pipeline_resume_dual_path.py` (AC #2) |
| `test_intake_reminder.sh` | `test_intake_reminder_new_layout.sh` (AC #4) |
| `test_session_start_bootstrap.sh` | `test_session_start_bootstrap_new_layout.sh` (AC #4) |
| `test_trace_prompt.sh` | `test_trace_prompt_new_layout.sh` (AC #4) |
| `test_workstream.bats` | covered by AC #8 (this slice) |
| `test_approval_token_path_migration.sh` | exists on integration tip |

End-to-end smoke is Slice F territory per Note #10 — F authors a
contrived `verify-per-task-subdirs-smoke` pipeline test that proves
items (a)–(g) compose. Slice E does NOT duplicate that.

Conclusion: 4 AC #8 stubs only. No gap-fill needed.

---
category: pattern
---

Concurrent isolation pattern modelled on `tests/test_allowlist_concurrency.py`:
8 simultaneous threads firing the hook, each producing a discrete
artifact, no interleaving. For Slice E, applied to per-task-subdir
fixtures: N parallel writers each writing to their own `pipeline-state/{task}/`
subdir. The atomic-write semantics come from the filesystem (each writer
owns its own subdir — no shared write surface), not from any locking.

---
category: decision
---

For `test_two_pipelines_no_state_collision`: use `make_pipeline_fixture`
to materialise both pipelines, exercise `find_pipeline_files` to confirm
both are discovered, then `shutil.rmtree` one subdir and re-query —
the other must still be discoverable. This proves per-task isolation.

For `test_concurrent_writes_isolate_per_task`: spawn N threads, each
calling `make_pipeline_fixture(task_id=f"t{i}")`. Verify all N
subdirs exist and each contains the expected pipeline.md file with
correct frontmatter. Multiprocessing not needed — file writes are
GIL-released so threads provide genuine concurrency on I/O.

For workstream tests: workstream-nested + root pipelines coexist; helper
returns the workstream version on collision (existing
`test_workstream_beats_root_on_task_id_collision` covers collision
case). Slice E adds the coexist-when-no-collision case + cleanup
isolation.
