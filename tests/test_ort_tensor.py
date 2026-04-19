"""Slice 5a: int64 tensor round-trip via CreateTensorWithDataAsOrtValue."""
import ctypes
import os
import sys
import unittest
from ctypes import POINTER, c_int64, c_void_p, cast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL = str(REPO_ROOT / "skills")
if _SKILL not in sys.path:
    sys.path.insert(0, _SKILL)

_DYLIB = "/opt/homebrew/lib/libonnxruntime.dylib"


def _env_ok():
    model = os.environ.get("BGE_MODEL_PATH")
    return Path(_DYLIB).exists() and bool(model) and Path(model).exists()


@unittest.skipUnless(_env_ok(), "ORT dylib/model not available")
class Int64TensorRoundTrip(unittest.TestCase):
    def test_create_then_read_ints_equal_input(self):
        from embedder._lib import model_io, ort_api, ort_dispatch, ort_session
        api = ort_api.load_api(_DYLIB)
        handle = ort_session.build(api, os.environ["BGE_MODEL_PATH"])
        try:
            ids = [101, 42, 7, 102]
            tensor, _arr = model_io.int64_tensor(api, ids, handle.mem_info)
            out_ptr = c_void_p()
            ort_dispatch.call(api, "GetTensorMutableData", tensor,
                              ctypes.byref(out_ptr))
            typed = cast(out_ptr, POINTER(c_int64 * len(ids))).contents
            self.assertEqual(list(typed), ids)
            ort_dispatch.call(api, "ReleaseValue", tensor)
        finally:
            ort_session.close(handle)


if __name__ == "__main__":
    unittest.main()
