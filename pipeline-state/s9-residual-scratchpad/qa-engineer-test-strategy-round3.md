---
category: pattern
---

Subprocess-based regression guards for module-import failures compose cleanly in a single test file when they share a harness. `tests/test_embedder_cli_dispatcher.py` now hosts three classes (`DispatcherRoutesCli`, `DispatcherRoutesBackfill`, `DoctorImportsLibAsQualified`), all reusing `_run`/`_env`/`_KWARGS`/`REPO_ROOT`. Each class asserts one failure-mode signature (`"No module named embedder.__main__"`, `"No module named '_lib'"`). Template for future module-resolution fixes: (1) subprocess with controlled `PYTHONPATH={repo}:{repo}/skills`, (2) `assertNotIn(signature, stdout+stderr)`, (3) new class per signature, (4) share harness.

---
category: discovery
---

Grep invariant for `skills/embedder/` bare `from _lib` imports is currently clean: `doctor.py:17` was the only occurrence, now protected by a sys.path prepend at lines 13-16 using `Path(__file__).resolve().parents[3] / "skills" / "reindex-memory"`. Resolution is cwd-independent because it keys off `__file__`, not `Path.cwd()`. Verified operationally from `/tmp` (exit 0, full doctor report).

---
category: warning
---

The subprocess test for `cli doctor` deliberately does NOT set `check=True` — doctor returns non-zero on degraded systems, which is normal reporting behavior, not a test failure. Only dispatcher-miss and `_lib`-miss failure signatures are asserted via `assertNotIn`. If a future hardener adds `check=True` to any of the three dispatcher tests, they must first filter out legitimate non-zero exits from doctor's verdict-based exit codes.
