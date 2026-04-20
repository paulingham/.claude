"""S10: embed_presence — model-file-presence gate + warn-once."""
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "skills"))
sys.path.insert(0, str(REPO_ROOT / "skills" / "reindex-memory"))

_MODEL_KEYS = ("ORT_DYLIB_PATH", "BGE_MODEL_PATH")


def _restore(key, value):
    if value is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = value


class _env:
    """Save/apply/restore model-path env vars around a test."""

    def __init__(self, ort=None, bge=None):
        self.ort = ort
        self.bge = bge

    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in _MODEL_KEYS}
        _restore("ORT_DYLIB_PATH", self.ort)
        _restore("BGE_MODEL_PATH", self.bge)
        from _lib import embed_presence
        embed_presence._reset_warn_cache()
        return self

    def __exit__(self, *a):
        for k, v in self._saved.items():
            _restore(k, v)
        from _lib import embed_presence
        embed_presence._reset_warn_cache()


class ModelsPresentGate(unittest.TestCase):
    def test_true_when_both_tempfiles_exist(self):
        with tempfile.TemporaryDirectory() as td:
            ort = Path(td) / "s.dylib"; ort.write_bytes(b"")
            bge = Path(td) / "s.onnx"; bge.write_bytes(b"")
            with _env(ort=str(ort), bge=str(bge)):
                from _lib import embed_presence
                self.assertTrue(embed_presence.models_present())

    def test_false_when_ort_path_nonexistent(self):
        with tempfile.TemporaryDirectory() as td:
            bge = Path(td) / "s.onnx"; bge.write_bytes(b"")
            with _env(ort="/nonexistent/s.dylib", bge=str(bge)):
                from _lib import embed_presence
                self.assertFalse(embed_presence.models_present())

    def test_false_when_bge_path_nonexistent(self):
        with tempfile.TemporaryDirectory() as td:
            ort = Path(td) / "s.dylib"; ort.write_bytes(b"")
            with _env(ort=str(ort), bge="/nonexistent/s.onnx"):
                from _lib import embed_presence
                self.assertFalse(embed_presence.models_present())


class WarnOnceOnMissingModel(unittest.TestCase):
    def test_warn_missing_emits_once_per_process(self):
        from _lib import embed_presence
        embed_presence._reset_warn_cache()
        buf = io.StringIO()
        with redirect_stderr(buf):
            for _ in range(3):
                embed_presence.warn_missing_once()
        self.assertEqual(buf.getvalue().count("not bootstrapped"), 1)


if __name__ == "__main__":
    unittest.main()
