"""D3: test_doctor_retrofit._ctx must preserve caller env vars.

Previously __enter__ popped ORT_DYLIB_PATH/BGE_MODEL_PATH without saving,
and __exit__ popped without restoring. Full-suite runs (alphabetical order)
wiped env before env-gated tests executed."""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_doctor_retrofit import _ctx  # noqa: E402


class CtxRestoresPreexistingEnv(unittest.TestCase):
    def test_env_vars_preserved_across_ctx(self):
        sentinel_ort = "/tmp/d3-sentinel-ort.dylib"
        sentinel_bge = "/tmp/d3-sentinel-bge.onnx"
        os.environ["ORT_DYLIB_PATH"] = sentinel_ort
        os.environ["BGE_MODEL_PATH"] = sentinel_bge
        try:
            with _ctx():
                pass
            self.assertEqual(os.environ.get("ORT_DYLIB_PATH"), sentinel_ort)
            self.assertEqual(os.environ.get("BGE_MODEL_PATH"), sentinel_bge)
        finally:
            os.environ.pop("ORT_DYLIB_PATH", None)
            os.environ.pop("BGE_MODEL_PATH", None)


if __name__ == "__main__":
    unittest.main()
