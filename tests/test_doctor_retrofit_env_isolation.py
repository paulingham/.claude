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


_KEYS = ("ORT_DYLIB_PATH", "BGE_MODEL_PATH")


class CtxRestoresPreexistingEnv(unittest.TestCase):
    def test_env_vars_preserved_across_ctx(self):
        prev = {k: os.environ.get(k) for k in _KEYS}
        try:
            self._run_assertion()
        finally:
            _restore_all(prev)

    def _run_assertion(self):
        os.environ["ORT_DYLIB_PATH"] = "/tmp/d3-sentinel-ort.dylib"
        os.environ["BGE_MODEL_PATH"] = "/tmp/d3-sentinel-bge.onnx"
        with _ctx():
            pass
        self.assertEqual(os.environ["ORT_DYLIB_PATH"],
                         "/tmp/d3-sentinel-ort.dylib")
        self.assertEqual(os.environ["BGE_MODEL_PATH"],
                         "/tmp/d3-sentinel-bge.onnx")


def _restore_all(prev):
    for k, v in prev.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


if __name__ == "__main__":
    unittest.main()
