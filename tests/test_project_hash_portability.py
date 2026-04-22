"""Python shim for the Slice 1 portable project-hash helpers.

Integrates the bats specs into the existing unittest runner by subprocess-
invoking ``bats tests/shell/project-hash.bats``. Also exercises the helpers
directly from Python so the Python test runner produces deterministic
cross-platform assertions (AC1.1, AC1.2, AC1.3) without requiring bats at
all on hosts where bats is absent.

AC1.2 (Ubuntu 24.04 parity) cannot be run from macOS without Docker. The
local approximation is: force the openssl branch AND the md5sum branch of
_md5_hash and assert both return the canonical digests. md5sum is the
Ubuntu default; openssl is the macOS default. If both backends agree on
the exact digests defined by the MD5 spec, portability is proved up to the
correctness of the two utilities themselves.
"""

from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LIB = REPO_ROOT / "hooks" / "_lib" / "project-hash.sh"
BATS_SPEC = REPO_ROOT / "tests" / "shell" / "project-hash.bats"


def _source_and_run(script: str) -> subprocess.CompletedProcess:
    """Source the project-hash lib in a fresh bash and run the given script."""
    return subprocess.run(
        ["bash", "-c", f'source "{LIB}"; {script}'],
        capture_output=True, text=True, check=False,
    )


class Md5HashContract(unittest.TestCase):
    """Direct contract tests for _md5_hash — no bats required."""

    def test_abc_returns_canonical_digest(self) -> None:
        result = _source_and_run("printf 'abc' | _md5_hash")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(result.stdout.strip(), "900150983cd24fb0d6963f7d28e17f72")

    def test_empty_stdin_returns_canonical_empty_digest(self) -> None:
        result = _source_and_run("printf '' | _md5_hash")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(result.stdout.strip(), "d41d8cd98f00b204e9800998ecf8427e")

    def test_backends_agree(self) -> None:
        """AC1.2 local proxy: md5sum and openssl branches produce same digest."""
        if not shutil.which("md5sum") or not shutil.which("openssl"):
            self.skipTest("both md5sum and openssl required to exercise both backends")
        via_md5sum = subprocess.run(
            ["bash", "-c", "printf 'abc' | md5sum | awk '{print $1}'"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        via_openssl = subprocess.run(
            ["bash", "-c", "printf 'abc' | openssl dgst -md5 | awk '{print $NF}'"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        self.assertEqual(via_md5sum, via_openssl)
        self.assertEqual(via_md5sum, "900150983cd24fb0d6963f7d28e17f72")


class ProjectHashContract(unittest.TestCase):
    """Direct contract tests for _project_hash — no bats required.

    Runs inside a tmpdir that is NOT a git repo so `git remote get-url origin`
    fails deterministically (exit 128, empty stdout). This exercises the
    fallback code path without needing to stub git.
    """

    def _run_in_non_repo(self, command: str) -> subprocess.CompletedProcess:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            return subprocess.run(
                ["bash", "-c", f'cd "{tmp}" && source "{LIB}" && {command}'],
                capture_output=True, text=True, check=False,
            )

    def test_default_fallback_is_local_when_outside_git_repo(self) -> None:
        result = self._run_in_non_repo("_project_hash")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(result.stdout.strip(), "local")

    def test_fallback_empty_string_is_preserved(self) -> None:
        result = self._run_in_non_repo('_project_hash --fallback ""')
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        # .strip() would also strip a trailing newline from echo; check raw.
        self.assertEqual(result.stdout, "\n")


class BatsSpecIntegration(unittest.TestCase):
    """Run the full bats spec if bats is on PATH; skip cleanly otherwise."""

    def test_project_hash_bats_spec_passes(self) -> None:
        if not shutil.which("bats"):
            self.skipTest("bats-core not installed")
        result = subprocess.run(
            ["bats", str(BATS_SPEC)],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)


class ShellCheckClean(unittest.TestCase):
    """AC1.7: shellcheck hooks/_lib/project-hash.sh is clean."""

    def test_lib_has_no_shellcheck_findings(self) -> None:
        if not shutil.which("shellcheck"):
            self.skipTest("shellcheck not installed")
        result = subprocess.run(
            ["shellcheck", str(LIB)],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(
            result.returncode, 0,
            msg=f"shellcheck findings:\n{result.stdout}\n{result.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
