"""Python shim that invokes the bats suite for session-lifecycle scripts.

Real assertions live in tests/shell/session-lifecycle.bats. This wrapper integrates
the bats run with the project's unittest runner so `python3 -m unittest
discover tests` exercises the shell specs too. Skips cleanly when bats-core
is not installed — matches tests/shell/run.sh behaviour.
"""

from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BATS_SPEC = REPO_ROOT / "tests" / "shell" / "session-lifecycle.bats"


class SessionLifecycleBatsSuite(unittest.TestCase):
    def test_bats_suite_passes(self) -> None:
        if shutil.which("bats") is None:
            self.skipTest("bats-core not installed (run scripts/install-tools.sh --yes)")
        result = subprocess.run(
            ["bats", str(BATS_SPEC)],
            capture_output=True,
            text=True,
            check=False,
            cwd=REPO_ROOT,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=f"bats failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )


class SessionLifecycleStaticChecks(unittest.TestCase):
    """Static checks for list-sessions.sh and remove-session.sh."""

    SCRIPTS_DIR = REPO_ROOT / "scripts"
    TARGETS = ("list-sessions.sh", "remove-session.sh")

    def _paths(self) -> list[Path]:
        return [self.SCRIPTS_DIR / t for t in self.TARGETS]

    def test_all_targets_pass_bash_n(self) -> None:
        for path in self._paths():
            with self.subTest(script=path.name):
                result = subprocess.run(
                    ["bash", "-n", str(path)],
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_shellcheck_clean_if_available(self) -> None:
        if shutil.which("shellcheck") is None:
            self.skipTest("shellcheck not installed")
        result = subprocess.run(
            ["shellcheck", *[str(p) for p in self._paths()]],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)

    def test_shape_line_budgets(self) -> None:
        budgets = {"list-sessions.sh": 45, "remove-session.sh": 45}
        for rel, limit in budgets.items():
            with self.subTest(script=rel):
                lines = (self.SCRIPTS_DIR / rel).read_text().splitlines()
                self.assertLessEqual(
                    len(lines), limit,
                    f"{rel}: {len(lines)} lines, limit {limit}",
                )


if __name__ == "__main__":
    unittest.main()
