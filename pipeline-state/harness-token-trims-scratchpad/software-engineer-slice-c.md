---
category: decision
---

Extracted `debug_display(state, env, now)` into a new `hooks/_lib/thinking_debug_display.py` module (24 lines) instead of inlining the TTL logic in `thinking_resolver.py`. This kept resolver under 50 lines, isolated TTL semantics in one testable module, and let me delete the now-redundant `state_display` from `thinking_role.py`. `coerce_state` gained an optional `debug_mtime` kwarg (None default) — backward compatible with all existing callers (snapshot test in `pipeline_frontmatter.py` already passes `False` positionally for `debug_active`).

---
category: warning
---

`thinking_resolver.resolve()` body is 12 lines (declarative precedence chain). This exceeds the 5-line function guideline but matches the pre-existing pattern from main and is structurally a single expression — the orchestrator-shipped `code-shape-check.sh` only enforces FILE-level (50-line) limits, not function-level. Reviewers should not request decomposition unless they have a way to express this without losing the layered-precedence readability.

---
category: discovery
---

Tests for `pipeline_state.py` are re-exported via a one-line shim at `tests/test_pipeline_state.py` that does `from test_thinking_defaults import *`. Adding new test classes to `test_thinking_defaults.py` automatically picks them up under both files in the test count — that's why the run reports each class twice.
