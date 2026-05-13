"""Test-suite-wide pytest conftest.

Side effect: prepend `${REPO_ROOT}/hooks/_lib` to `sys.path` so test files
can import sandbox-verify (and future) helpers without per-file
`sys.path.insert(...)` boilerplate. Pytest auto-loads any `conftest.py`
in the test root before collecting any test file in that directory.

History: Story 1 of the sandbox-verify epic spawned a fix-engineer to add
per-file `sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))` lines.
Story 2 (this file) makes that the conftest's responsibility instead, so
Story 3/4 authors do not need to remember the boilerplate.

Idempotency: the insert is gated on `not in sys.path` so re-loads (e.g.
pytest's `--collect-only` followed by a normal run) do not duplicate
entries.
"""
import sys
from pathlib import Path

_HOOKS_LIB = str(Path(__file__).resolve().parent.parent / "hooks" / "_lib")
if _HOOKS_LIB not in sys.path:
    sys.path.insert(0, _HOOKS_LIB)
