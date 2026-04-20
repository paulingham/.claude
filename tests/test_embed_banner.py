"""S10: embed_banner.line() renders capture-gate state for doctor."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "skills"))
sys.path.insert(0, str(REPO_ROOT / "skills" / "reindex-memory"))

_KEYS = ("ORT_DYLIB_PATH", "BGE_MODEL_PATH", "CLAUDE_EMBEDDER_STATUS")


def _restore(k, v):
    if v is None:
        os.environ.pop(k, None)
    else:
        os.environ[k] = v


class _Env:
    def __init__(self, ort, bge, status_path=None):
        self.ort, self.bge, self.status_path = ort, bge, status_path

    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in _KEYS}
        _restore("ORT_DYLIB_PATH", self.ort)
        _restore("BGE_MODEL_PATH", self.bge)
        _restore("CLAUDE_EMBEDDER_STATUS", self.status_path)
        return self

    def __exit__(self, *a):
        for k, v in self._saved.items():
            _restore(k, v)


class EmbedBannerLine(unittest.TestCase):
    def test_off_when_models_missing(self):
        with _Env("/nonexistent/s.dylib", "/nonexistent/s.onnx"):
            from _lib import embed_banner
            self.assertEqual(embed_banner.line(),
                             "embed: off (no model — run /project-setup)")

    def test_on_pending_when_models_present_but_no_success_yet(self):
        with tempfile.TemporaryDirectory() as td:
            ort = Path(td) / "s.dylib"; ort.write_bytes(b"")
            bge = Path(td) / "s.onnx"; bge.write_bytes(b"")
            status = Path(td) / "status.json"; status.write_text("{}")
            with _Env(str(ort), str(bge), str(status)):
                from _lib import embed_banner
                self.assertEqual(embed_banner.line(),
                                 "embed: on (pending first write)")

    def test_on_when_last_success_recorded(self):
        with tempfile.TemporaryDirectory() as td:
            ort = Path(td) / "s.dylib"; ort.write_bytes(b"")
            bge = Path(td) / "s.onnx"; bge.write_bytes(b"")
            status = Path(td) / "status.json"
            status.write_text('{"last_success_at": "2026-04-20T00:00:00Z"}')
            with _Env(str(ort), str(bge), str(status)):
                from _lib import embed_banner
                self.assertEqual(embed_banner.line(), "embed: on")


if __name__ == "__main__":
    unittest.main()
