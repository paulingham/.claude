"""Embedder facade tests. See also test_embedder_lifecycle.py / facade."""
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL = str(REPO_ROOT / "skills")
if _SKILL not in sys.path:
    sys.path.insert(0, _SKILL)


class ResetCallsCloseOnSingleton(unittest.TestCase):
    def test_reset_invokes_close_method_when_present(self):
        from embedder import embedder as facade
        closer = mock.Mock()
        facade._singleton = mock.Mock(close=closer)
        facade.reset_singleton_for_tests()
        closer.assert_called_once()


if __name__ == "__main__":
    unittest.main()
