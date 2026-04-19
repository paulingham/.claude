"""Slice 9: doctor reports degraded on win32 (POSIX-only guard, surface 3)."""
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL = str(REPO_ROOT / "skills")
if _SKILL not in sys.path:
    sys.path.insert(0, _SKILL)


class DoctorOnWindowsReportsDegraded(unittest.TestCase):
    def test_verdict_mentions_windows_not_supported(self):
        from embedder._lib import doctor
        with mock.patch.object(sys, "platform", "win32"):
            out = doctor.report()
        self.assertIn("windows_not_supported", out)
        self.assertIn("verdict: degraded", out)

    def test_posix_does_not_emit_windows_guard(self):
        from embedder._lib import doctor
        with mock.patch.object(sys, "platform", "darwin"):
            out = doctor.report()
        self.assertNotIn("windows_not_supported", out)


if __name__ == "__main__":
    unittest.main()
