---
id: instinct-env-var-test-hygiene
confidence: 0.6
domain: testing
scope: project
project: 8efffd88329f34786e1828737702e911
roles: [software-engineer, qa-engineer, code-reviewer]
source: review-feedback
created: 2026-04-20T07:45:00Z
evidence_count: 2
last_seen: 2026-04-20T13:45:00Z
---

## Pattern
Tests that mutate `os.environ` or patch module-level state MUST use save→modify→restore (or `unittest.mock.patch.dict` / `addCleanup(patcher.stop)`) — never bare `pop()`, never `patch.start()` without cleanup.

## Why
Env-gated test suites run fine alone but cascade-fail under full `unittest discover` when caller env vars bleed between tests. Leaked mocks on native-dispatch targets (e.g., ctypes) produce SIGSEGV, not a clean AssertionError, making the root cause hard to find.

## Evidence
- 2026-04-20 (S5.1 D7): Four independent bugs all in the same class:
  - `test_doctor_retrofit._ctx` popped ORT_DYLIB_PATH/BGE_MODEL_PATH without saving → wiped caller env
  - `test_live_writer_embed` set BGE_MODEL_PATH to a corrupt file and popped on cleanup
  - `test_model_io_tensor` used `mock.patch.start()` without `addCleanup(patcher.stop)` → MagicMock leaked into `model_io.ort_dispatch`, later tests hit ctypes through the mock → SIGSEGV
  - `test_embed_gate_status` / `test_embedder_real_stub` / `test_recall_banner` assumed env was unset
- Surfaced only under `python3 -m unittest discover -s tests` with real env vars set; passed in CI profile and when run individually
- 2026-04-20 (S9 reinforcement): Code-reviewer audit confirmed all 24 new S9 tests correctly use `patch.dict(os.environ, ..., clear=False)` — no bare `os.environ.pop`, no `patch.start()` without cleanup, no leaks between tests. Instinct applied proactively during build; zero violations caught in review. Pattern is now the project default.

## How to apply
- Build: for any test that sets or unsets an env var, use `_saved = {k: os.environ.get(k) for k in MANAGED}` / try / restore, or a `_scope` context manager
- Build: for any `mock.patch(...).start()`, pair with `self.addCleanup(patcher.stop)` immediately — never separated by conditional logic
- Code-review: flag bare `os.environ.pop` inside test `finally` blocks as a bleed risk
- Module singletons with env-dependent caches need `_reset_singleton_for_tests()` helpers and tests must call them after env changes
- QA: any env-gated test suite must pass under full `discover` mode with env vars both set and unset before shipping
