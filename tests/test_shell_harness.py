"""Meta-tests for tests/shell/run.sh — the bats wrapper.

The wrapper must:
  * Exit 0 with a SKIP message when bats is absent (default mode).
  * Exit non-zero when bats is absent AND --require-bats is passed (CI mode).
  * Invoke bats on discovered .bats files when bats is present.

Tests subprocess-invoke run.sh with a controlled PATH so we can simulate
both "bats absent" and "bats present" without depending on the host system.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RUN_SH = REPO_ROOT / "tests" / "shell" / "run.sh"


def _empty_path_env(tmp: Path) -> dict:
    """Return an env with PATH pointing at an empty dir so `bats` is absent."""
    env = os.environ.copy()
    # Keep /usr/bin + /bin so bash, env, etc. still resolve; bats is not there.
    env["PATH"] = f"{tmp}:/usr/bin:/bin"
    return env


def _stub_bats_env(tmp: Path, exit_code: int = 0) -> tuple[dict, Path]:
    """Create a PATH containing a stub `bats` that records args + exits."""
    log_file = tmp / "args.log"
    stub = tmp / "bats"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        f'printf "%s\\n" "$@" > "{log_file}"\n'
        f"exit {exit_code}\n"
    )
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    env = os.environ.copy()
    env["PATH"] = f"{tmp}:/usr/bin:/bin"
    return env, log_file


class _TmpDirCase(unittest.TestCase):
    """Base test case that provisions and cleans up a scratch directory."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="claude-shell-harness-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)


class RunShBatsAbsent(_TmpDirCase):
    def test_exits_zero_with_skip_message_when_bats_missing(self) -> None:
        result = subprocess.run(
            ["bash", str(RUN_SH)],
            env=_empty_path_env(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("SKIP: bats-core not installed", result.stdout + result.stderr)

    def test_require_bats_flag_exits_nonzero_when_bats_missing(self) -> None:
        result = subprocess.run(
            ["bash", str(RUN_SH), "--require-bats"],
            env=_empty_path_env(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("bats-core not installed", result.stdout + result.stderr)


class RunShBatsPresent(_TmpDirCase):
    def test_invokes_bats_with_shell_bats_files_when_present(self) -> None:
        env, log_file = _stub_bats_env(self.tmp, exit_code=0)
        result = subprocess.run(
            ["bash", str(RUN_SH)],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertTrue(log_file.exists(), "stub bats was not invoked")
        recorded_args = log_file.read_text().splitlines()
        self.assertTrue(
            any(arg.endswith(".bats") or "shell" in arg for arg in recorded_args),
            f"bats was not passed any .bats targets: {recorded_args!r}",
        )


class HelpersBash(unittest.TestCase):
    """Sanity-check the source-once helpers shipped alongside run.sh.

    We source helpers.bash inside a bash subprocess and verify each helper's
    contract. Full behavioural tests live in bats specs (added in later
    slices); this fixes the API surface so downstream slices can rely on it.
    """

    HELPERS = REPO_ROOT / "tests" / "shell" / "helpers.bash"

    def _run_bash(self, script: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", "-c", f'set -e; source "{self.HELPERS}"; {script}'],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_cli_assert_ok_passes_for_zero_exit(self) -> None:
        result = self._run_bash("cli_assert_ok true")
        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_cli_assert_ok_fails_for_nonzero_exit(self) -> None:
        # Disable `set -e` for this assertion: we expect the helper itself
        # to return non-zero, not to abort the surrounding script.
        result = self._run_bash("set +e; cli_assert_ok false; echo rc=$?")
        self.assertIn("rc=1", result.stdout)

    def test_cli_assert_stdout_match_passes_on_match(self) -> None:
        result = self._run_bash(
            "cli_assert_stdout_match 'hello' echo hello world"
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_cli_assert_stdout_match_fails_on_no_match(self) -> None:
        result = self._run_bash(
            "set +e; cli_assert_stdout_match 'nope' echo hello world; echo rc=$?"
        )
        self.assertIn("rc=1", result.stdout)


class HarnessArtifacts(unittest.TestCase):
    """Required files that make the harness self-describing and discoverable."""

    SHELL_DIR = REPO_ROOT / "tests" / "shell"

    def test_bats_root_marker_exists(self) -> None:
        self.assertTrue(
            (self.SHELL_DIR / ".bats-root").exists(),
            "tests/shell/.bats-root marker missing",
        )

    def test_hooks_tests_fixtures_dir_exists(self) -> None:
        fixtures = REPO_ROOT / "hooks" / "tests" / "fixtures"
        self.assertTrue(
            fixtures.is_dir(),
            "hooks/tests/fixtures/ directory missing (Slice 1 needs it)",
        )

    def test_readme_documents_run_sh_and_prerequisites(self) -> None:
        readme = self.SHELL_DIR / "README.md"
        self.assertTrue(readme.exists(), "tests/shell/README.md missing")
        body = readme.read_text()
        for keyword in ("bats", "run.sh", "--require-bats"):
            self.assertIn(keyword, body, f"README missing reference to {keyword!r}")


if __name__ == "__main__":
    unittest.main()
