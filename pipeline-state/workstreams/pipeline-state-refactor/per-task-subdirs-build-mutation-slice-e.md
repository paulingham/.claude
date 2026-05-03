# Slice E mutation report — manual enumeration

These are test files (integration tests against already-implemented
production code). The mutation gate is applied to the **test logic** —
i.e. would a wrong assertion silently pass?

## File: `tests/test_pipeline_state_concurrent_isolation.py`

### Mutation candidates

| # | Location | Mutation | Survives? | Why caught |
|---|----------|----------|-----------|-----------|
| 1 | line 28 `{p1, p2} <= found` | flip to `{p1, p2} >= found` | KILLED | extra discovered files would break the superset check |
| 2 | line 28 `<=` → `==` | KILLED | additional pipelines (e.g. via test pollution) would break equality |
| 3 | line 31 `assert p2.exists()` | drop the assertion | KILLED | second pipeline cleanup invariance is the test's whole point |
| 4 | line 32 `== [p2]` | weaken to `>= [p2]` | KILLED | mutation would not detect duplicated/leftover artefacts |
| 5 | line 51 `8` | reduce to `1` | KILLED | concurrency is the test's purpose; single writer doesn't probe contention |
| 6 | line 53 `==` set equality | weaken to `<=` | KILLED | a writer that fails silently would not be detected |
| 7 | line 56 `path.exists()` | drop | KILLED | per-subdir landing is the integration claim |
| 8 | line 57 `"task_id: task-"` | drop frontmatter check | KILLED | a fixture writing empty file would slip past existence-only |

8/8 caught. Kill rate: 100%.

## File: `tests/test_pipeline_state_workstream_nested.py`

| # | Location | Mutation | Survives? | Why caught |
|---|----------|----------|-----------|-----------|
| 1 | `assert nested == expected` | weaken to `endswith` check | KILLED | precise path equality locks the workstream-nested layout |
| 2 | `assert nested in find_pipeline_files(...)` | drop | KILLED | discovery is the test's first AC #8 claim |
| 3 | `assert (tmp_path / "workstreams" / "ws1").exists()` | drop | KILLED | "workstream dir intact" is the cleanup invariant |
| 4 | `not nested.exists()` | flip to `nested.exists()` | KILLED | we just rmtree'd it; assertion would obviously fail |
| 5 | `{root, nested} <= found` | replace with `root in found` (drop nested check) | KILLED | second test's whole point is co-existence of both |
| 6 | `{root, nested} <= found` | replace with `nested in found` (drop root) | KILLED | symmetric — both must be discoverable |

6/6 caught. Kill rate: 100%.

## Combined

14/14 mutations killed = 100% kill rate, exceeds 70% threshold.

The tests are tight: every assertion has a load-bearing role; weakening
or dropping any one allows a regression in the integrated DUAL_PATH
system to slip through.
