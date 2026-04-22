"""Python shim that invokes the bats suite for scripts/install-tools.sh.

The real assertions live in tests/shell/install-tools.bats. This wrapper
integrates the bats run with the project's unittest runner so a single
`python3 -m unittest discover tests` exercises both Python and shell specs.

Skips cleanly when bats-core is not installed — matches tests/shell/run.sh
behaviour so the suite stays green on fresh clones that have not yet run
scripts/install-tools.sh.
"""

from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BATS_SPEC = REPO_ROOT / "tests" / "shell" / "install-tools.bats"


class InstallToolsBatsSuite(unittest.TestCase):
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


class InstallToolsStaticChecks(unittest.TestCase):
    """Static checks that do not require bats to be installed."""

    SCRIPTS_DIR = REPO_ROOT / "scripts"

    def test_all_shell_scripts_pass_bash_n(self) -> None:
        shell_files = [
            self.SCRIPTS_DIR / "install-tools.sh",
            *(self.SCRIPTS_DIR / "_lib").glob("*.sh"),
        ]
        for path in shell_files:
            with self.subTest(script=path.name):
                result = subprocess.run(
                    ["bash", "-n", str(path)],
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_shellcheck_clean_if_available(self) -> None:
        if shutil.which("shellcheck") is None:
            self.skipTest("shellcheck not installed")
        targets = [str(self.SCRIPTS_DIR / "install-tools.sh"), *[
            str(p) for p in (self.SCRIPTS_DIR / "_lib").glob("*.sh")
        ]]
        result = subprocess.run(
            ["shellcheck", *targets], capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)

    def test_readme_documents_flags_env_and_manual_smoke(self) -> None:
        readme = self.SCRIPTS_DIR / "README.md"
        body = readme.read_text()
        for keyword in (
            "--dry-run", "--yes", "CLAUDE_VENV_PATH", "PIP_CMD",
            "OS_RELEASE_PATH", "INSTALL_PKG_CMD_PRINTER",
            "ubuntu:24.04", "AC3.9",
        ):
            self.assertIn(keyword, body, f"scripts/README.md missing: {keyword!r}")


if __name__ == "__main__":
    unittest.main()
