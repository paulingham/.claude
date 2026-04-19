"""Slice 2: load ORT dylib via CFUNCTYPE, version-gate >=1.17."""
import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL = str(REPO_ROOT / "skills")
if _SKILL not in sys.path:
    sys.path.insert(0, _SKILL)


_DYLIB = "/opt/homebrew/lib/libonnxruntime.dylib"


def _dylib_available():
    return Path(_DYLIB).exists()


@unittest.skipUnless(_dylib_available(), "ORT dylib not installed")
class LoadApi(unittest.TestCase):
    def test_load_returns_nonzero_pointer(self):
        from embedder._lib import ort_api
        api_ptr = ort_api.load_api(_DYLIB)
        self.assertTrue(bool(api_ptr.value))


class VersionGate(unittest.TestCase):
    def test_old_version_raises(self):
        from embedder._lib import ort_api
        from embedder._lib import paths
        with self.assertRaises(paths.EmbedderUnavailable):
            ort_api._version_gate(b"1.16.3")

    def test_new_version_passes(self):
        from embedder._lib import ort_api
        ort_api._version_gate(b"1.24.4")  # no exception


if __name__ == "__main__":
    unittest.main()
