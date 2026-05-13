"""Contract — `tests/conftest.py` prepends `hooks/_lib` to `sys.path` so
new test files can import sandbox-verify (and future) helpers without
duplicating `sys.path.insert(...)` boilerplate.

Pytest auto-loads any `conftest.py` at or above the collected test's
directory. The conftest in `tests/` is loaded once per test session and
its side-effects (sys.path manipulation, fixtures, plugins) apply to
every test file in `tests/`.

This test asserts both the FILE existence AND the side-effect (the path
ends up in `sys.path` at collection time). Story 1 spawned a fix-engineer
to add `sys.path.insert` lines inside each new test file (sibling
pattern); Story 2's conftest is the future-proofing seam that lets Story
3/4 author tests without the boilerplate.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOKS_LIB = REPO_ROOT / "hooks" / "_lib"
CONFTEST = REPO_ROOT / "tests" / "conftest.py"


class ConftestPrependsHooksLibToSysPath(unittest.TestCase):
    """`tests/conftest.py` must exist AND must have placed
    `${REPO_ROOT}/hooks/_lib` onto `sys.path` by the time this test
    is collected.
    """

    def test_conftest_file_exists(self):
        self.assertTrue(
            CONFTEST.exists(),
            "tests/conftest.py must exist (Story-2 import-seam contract)")

    def test_conftest_prepends_hooks_lib_to_sys_path(self):
        # The conftest is loaded by pytest before any test file in
        # tests/ runs; by this point, the resolved hooks_lib path must
        # be present in sys.path.
        hooks_lib_str = str(HOOKS_LIB)
        resolved = [str(Path(p).resolve()) if p else p for p in sys.path]
        self.assertIn(
            hooks_lib_str, resolved,
            f"tests/conftest.py must prepend `{hooks_lib_str}` to "
            f"sys.path so new tests can import `sandbox_verify_*` and "
            f"future hooks/_lib modules without per-file boilerplate")


if __name__ == "__main__":
    unittest.main()
