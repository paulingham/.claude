"""Slice 5a/5d: model_io encode_model_path + platform guard."""
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL = str(REPO_ROOT / "skills")
if _SKILL not in sys.path:
    sys.path.insert(0, _SKILL)


class EncodeModelPath(unittest.TestCase):
    def test_posix_path_returns_utf8_bytes(self):
        from embedder._lib import model_io
        out = model_io.encode_model_path("/tmp/x/model.onnx")
        self.assertEqual(out, b"/tmp/x/model.onnx")

    def test_non_ascii_path_encoded_utf8(self):
        from embedder._lib import model_io
        out = model_io.encode_model_path("/tmp/café/模型.onnx")
        self.assertEqual(out, "/tmp/café/模型.onnx".encode("utf-8"))


class WindowsGuard(unittest.TestCase):
    def test_win32_raises_embedder_unavailable(self):
        from embedder._lib import model_io
        from embedder._lib import paths
        with mock.patch.object(sys, "platform", "win32"):
            with self.assertRaises(paths.EmbedderUnavailable):
                model_io.encode_model_path("/tmp/x.onnx")


if __name__ == "__main__":
    unittest.main()
