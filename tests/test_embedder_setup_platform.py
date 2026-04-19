"""Slice 9: setup entrypoint exits early on win32 (POSIX surface 2)."""
import io
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL = str(REPO_ROOT / "skills")
if _SKILL not in sys.path:
    sys.path.insert(0, _SKILL)


class SetupOnWindowsExitsEarly(unittest.TestCase):
    def test_win32_returns_nonzero_exit_with_clear_message(self):
        from embedder._lib import cli_actions
        buf = io.StringIO()
        with mock.patch.object(sys, "platform", "win32"), \
                mock.patch.object(sys, "stdout", buf):
            rc = cli_actions.setup()
        self.assertEqual(rc, 1)
        self.assertIn("Windows is not supported", buf.getvalue())
        self.assertIn("WSL", buf.getvalue())

    def test_posix_setup_returns_zero(self):
        from embedder._lib import cli_actions
        with mock.patch.object(sys, "platform", "darwin"), \
                mock.patch.object(sys, "stdout", io.StringIO()):
            rc = cli_actions.setup()
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
