"""S10: co-equivalence — _path_ok agrees with embedder/_lib/paths resolvers.

Guards against drift between the two sibling implementations of
"env + exists" logic. If this test breaks, the bodies of
_lib/embed_presence._path_ok and embedder._lib.paths._resolve_env
have diverged.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "skills"))
sys.path.insert(0, str(REPO_ROOT / "skills" / "reindex-memory"))

_KEYS = ("ORT_DYLIB_PATH", "BGE_MODEL_PATH")


def _restore(k, v):
    if v is None:
        os.environ.pop(k, None)
    else:
        os.environ[k] = v


class _Env:
    def __init__(self, ort, bge):
        self.ort, self.bge = ort, bge

    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in _KEYS}
        _restore("ORT_DYLIB_PATH", self.ort)
        _restore("BGE_MODEL_PATH", self.bge)
        return self

    def __exit__(self, *a):
        for k, v in self._saved.items():
            _restore(k, v)


def _resolvers_succeed():
    from embedder._lib import paths
    try:
        paths.resolve_dylib()
        paths.resolve_model()
        return True
    except paths.EmbedderUnavailable:
        return False


class PresenceAgreesWithPathsResolver(unittest.TestCase):
    def test_both_set_valid_both_agree_true(self):
        with tempfile.TemporaryDirectory() as td:
            ort = Path(td) / "s.dylib"; ort.write_bytes(b"")
            bge = Path(td) / "s.onnx"; bge.write_bytes(b"")
            with _Env(str(ort), str(bge)):
                from _lib import embed_presence
                self.assertTrue(embed_presence.models_present())
                self.assertTrue(_resolvers_succeed())

    def test_ort_missing_both_agree_false(self):
        with tempfile.TemporaryDirectory() as td:
            bge = Path(td) / "s.onnx"; bge.write_bytes(b"")
            with _Env("/nonexistent/s.dylib", str(bge)):
                from _lib import embed_presence
                self.assertFalse(embed_presence.models_present())
                self.assertFalse(_resolvers_succeed())

    def test_bge_missing_both_agree_false(self):
        with tempfile.TemporaryDirectory() as td:
            ort = Path(td) / "s.dylib"; ort.write_bytes(b"")
            with _Env(str(ort), "/nonexistent/s.onnx"):
                from _lib import embed_presence
                self.assertFalse(embed_presence.models_present())
                self.assertFalse(_resolvers_succeed())

    def test_ort_unset_both_agree_false(self):
        with _Env(None, None):
            from _lib import embed_presence
            self.assertFalse(embed_presence.models_present())
            self.assertFalse(_resolvers_succeed())



    def test_bge_unset_ort_valid_both_agree(self):
        """BGE_MODEL_PATH unset exercises default-path fallback; both agree on result."""
        with tempfile.TemporaryDirectory() as td:
            ort = Path(td) / "s.dylib"; ort.write_bytes(b"")
            with _Env(str(ort), None):
                from _lib import embed_presence
                self.assertEqual(embed_presence.models_present(), _resolvers_succeed())


if __name__ == "__main__":
    unittest.main()
