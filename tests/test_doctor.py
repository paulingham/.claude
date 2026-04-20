"""Tests for embedder._lib.doctor.

Behavioural coverage for the doctor module lives in:
  - test_doctor_retrofit.py (6-field render + verdict wiring)
  - test_embedder_doctor_platform.py (POSIX-only guard — win32 degraded)

This file exists to pair with _lib/doctor.py and guards the public API
surface: report() must return a string and emit a verdict line.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL = str(REPO_ROOT / "skills")
_REINDEX = str(REPO_ROOT / "skills" / "reindex-memory")
for p in (_SKILL, _REINDEX):
    if p not in sys.path:
        sys.path.insert(0, p)


class DoctorReportContract(unittest.TestCase):
    def test_report_returns_string_with_verdict_line(self):
        from embedder._lib import doctor
        out = doctor.report()
        self.assertIsInstance(out, str)
        self.assertIn("verdict:", out)


class DoctorIncludesEmbedBanner(unittest.TestCase):
    def test_report_contains_embed_line(self):
        from embedder._lib import doctor
        out = doctor.report()
        self.assertIn("embed:", out)


if __name__ == "__main__":
    unittest.main()
