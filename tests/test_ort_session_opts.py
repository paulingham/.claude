"""Unit cover for ort_session_opts (fake dispatch)."""
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL = str(REPO_ROOT / "skills")
if _SKILL not in sys.path:
    sys.path.insert(0, _SKILL)


class BuildOptionsCallsExpectedOps(unittest.TestCase):
    def test_invokes_create_then_threads_then_opt_level(self):
        from embedder._lib import ort_session_opts
        with mock.patch.object(ort_session_opts, "ort_dispatch") as disp:
            ort_session_opts.build_options("api")
            ops = [c.args[1] for c in disp.call.call_args_list]
            self.assertEqual(ops, [
                "CreateSessionOptions",
                "SetIntraOpNumThreads",
                "SetSessionGraphOptimizationLevel"])


if __name__ == "__main__":
    unittest.main()
