"""Slice 3a/3b: dispatch.call — happy path + error raising + Release."""
import os
import sys
import unittest
from ctypes import c_void_p
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL = str(REPO_ROOT / "skills")
if _SKILL not in sys.path:
    sys.path.insert(0, _SKILL)

_DYLIB = "/opt/homebrew/lib/libonnxruntime.dylib"


def _available():
    return Path(_DYLIB).exists()


@unittest.skipUnless(_available(), "ORT dylib not installed")
class DispatchHappyPath(unittest.TestCase):
    def test_create_env_returns_none_and_fills_handle(self):
        import ctypes
        from embedder._lib import ort_api, ort_dispatch
        api = ort_api.load_api(_DYLIB)
        env_out = ctypes.c_void_p()
        rc = ort_dispatch.call(api, "CreateEnv", 2, b"test",
                               ctypes.byref(env_out))
        self.assertIsNone(rc)
        self.assertTrue(bool(env_out.value))
        ort_dispatch.call(api, "ReleaseEnv", env_out)


@unittest.skipUnless(_available(), "ORT dylib not installed")
class DispatchRaisesOnStatus(unittest.TestCase):
    def test_create_session_with_missing_file_raises(self):
        import ctypes
        from embedder._lib import ort_api, ort_dispatch
        from embedder._lib import paths
        api = ort_api.load_api(_DYLIB)
        env = ctypes.c_void_p()
        opts = ctypes.c_void_p()
        sess = ctypes.c_void_p()
        ort_dispatch.call(api, "CreateEnv", 2, b"t", ctypes.byref(env))
        ort_dispatch.call(api, "CreateSessionOptions", ctypes.byref(opts))
        try:
            with self.assertRaises(paths.EmbedderRuntimeError) as cm:
                ort_dispatch.call(api, "CreateSession", env,
                                  b"/nonexistent/model.onnx",
                                  opts, ctypes.byref(sess))
            self.assertIn("ORT:", str(cm.exception))
        finally:
            ort_dispatch.call(api, "ReleaseSessionOptions", opts)
            ort_dispatch.call(api, "ReleaseEnv", env)


@unittest.skipUnless(_available(), "ORT dylib not installed")
class ReleaseShortCircuits(unittest.TestCase):
    def test_release_null_is_noop(self):
        import ctypes
        from embedder._lib import ort_api, ort_dispatch
        api = ort_api.load_api(_DYLIB)
        # Releasing NULL value handle is documented as a no-op in ORT
        result = ort_dispatch.call(api, "ReleaseValue", ctypes.c_void_p(0))
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
