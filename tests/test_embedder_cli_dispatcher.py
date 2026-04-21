"""S9-residual M1: `python3 -m embedder {cli,backfill}` dispatcher.

The documented invocations `python3 -m embedder cli doctor` and
`python3 -m embedder backfill` previously failed with
`No module named embedder.__main__`. A thin `__main__.py` dispatcher
routes subcommands to the existing top-level modules (embedder.cli,
embedder.backfill) so the docs are executable.
"""
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_DISPATCHER_MISS = "No module named embedder.__main__"
_LIB_MISS = "No module named '_lib'"


def _env():
    return {**os.environ,
            "PYTHONPATH": f"{REPO_ROOT}:{REPO_ROOT}/skills"}


_KWARGS = dict(capture_output=True, text=True, timeout=30)


def _run(args):
    cmd = [sys.executable, "-m", "embedder", *args]
    try:
        return subprocess.run(cmd, env=_env(), cwd=str(REPO_ROOT), **_KWARGS)
    except subprocess.TimeoutExpired as exc:
        raise AssertionError(f"timeout: {exc}") from exc


class DispatcherRoutesCli(unittest.TestCase):
    def test_cli_doctor_does_not_raise_module_not_found(self):
        result = _run(["cli", "doctor"])
        combined = result.stdout + result.stderr
        self.assertNotIn(_DISPATCHER_MISS, combined)


class DispatcherRoutesBackfill(unittest.TestCase):
    def test_backfill_help_does_not_raise_module_not_found(self):
        result = _run(["backfill", "--help"])
        combined = result.stdout + result.stderr
        self.assertNotIn(_DISPATCHER_MISS, combined)


class DoctorImportsLibAsQualified(unittest.TestCase):
    def test_cli_doctor_does_not_raise_lib_not_found(self):
        result = _run(["cli", "doctor"])
        combined = result.stdout + result.stderr
        self.assertNotIn(_LIB_MISS, combined)


if __name__ == "__main__":
    unittest.main()
