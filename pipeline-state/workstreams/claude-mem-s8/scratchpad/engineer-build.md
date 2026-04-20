---
category: decision
---
S8 flip implemented as `os.environ.get("CLAUDE_EMBED_AT_CAPTURE", "1") == "0"` (default "1", opt-out on "0"). This preserves the old negated-comparison shape of the guard (single expression, single line) and ensures only the literal string "0" disables embedding — any other value (including empty string) triggers embedding.

---
category: discovery
---
The `skills/reindex-memory/_lib/` directory is hyphenated, so `_lib` is NOT importable as `skills.reindex_memory._lib`. Tests rely on `tests/_support.py` which prepends `skills/reindex-memory` to sys.path, making `from _lib import embed_gate` the only valid direct-import form in tests.

---
category: pattern
---
The existing test file pairs a `try/finally` env restoration with a helper method (`_assert_...`) to keep each test method body tight while still honoring the env-var-test-hygiene instinct. New tests in this file follow that same shape — env save/restore in the test method, assertions in a helper.

---
category: warning
---
The old `DefaultCaptureSkipsEmbedder` test asserted BOTH zero-cost import AND zero embedding rows. After the flip, the zero-import invariant MOVED to the opt-out path (=0). The renamed `OptOutSkipsEmbedder` preserves both assertions but under the new opt-out trigger. If a future change makes embed-on-default lazily import only on success, the `DefaultPathAttemptsEmbed` test will break — that's correct behavior: AC1 says default must import-and-attempt, not import-if-ready.
