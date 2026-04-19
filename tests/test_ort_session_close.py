"""Unit tests for close-release helpers (per-field error-tolerant release)."""
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL = str(REPO_ROOT / "skills")
if _SKILL not in sys.path:
    sys.path.insert(0, _SKILL)


class _Ptr:
    def __init__(self, v):
        self.value = v


class TryReleaseSwallowsAndReturnsException(unittest.TestCase):
    def test_returns_exception_when_dispatch_raises(self):
        from embedder._lib import ort_session_close
        with mock.patch.object(ort_session_close.ort_dispatch, "call",
                               side_effect=RuntimeError("boom")):
            handle = mock.Mock(api="api", session=_Ptr(1))
            err = ort_session_close.try_release(handle, "session",
                                                "ReleaseSession")
        self.assertIsInstance(err, RuntimeError)

    def test_returns_none_on_success(self):
        from embedder._lib import ort_session_close
        with mock.patch.object(ort_session_close.ort_dispatch,
                               "call"):
            handle = mock.Mock(api="api", session=_Ptr(1))
            self.assertIsNone(ort_session_close.try_release(
                handle, "session", "ReleaseSession"))


if __name__ == "__main__":
    unittest.main()
