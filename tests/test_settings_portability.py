"""Python shim that invokes the bats suite for Slice 2 settings portability.

The real assertions live in tests/shell/settings-portability.bats. This
wrapper integrates the bats run with the project's unittest runner so a
single `python3 -m unittest discover tests` exercises both Python and
shell specs.

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
BATS_SPEC = REPO_ROOT / "tests" / "shell" / "settings-portability.bats"


class SettingsPortabilityBatsSuite(unittest.TestCase):
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
