"""Model path + tensor ctypes helpers. POSIX-only; Windows guarded."""
import ctypes
import sys
from ctypes import POINTER, c_float, c_int64, c_size_t, c_void_p, cast

from embedder._lib import ort_dispatch
from embedder._lib.paths import EmbedderUnavailable

_INT64 = 7  # ONNX_TENSOR_ELEMENT_DATA_TYPE_INT64


def encode_model_path(path_str):
    if sys.platform == "win32":
        raise EmbedderUnavailable("Windows not supported; use WSL")
    return str(path_str).encode("utf-8")


def int64_tensor(api, ids, mem_info):
    arr = (c_int64 * len(ids))(*ids)
    shape = (c_int64 * 2)(1, len(ids))
    out = c_void_p()
    _create_int64(api, mem_info, arr, shape, out)
    return out, arr


def _create_int64(api, mem_info, arr, shape, out):
    nbytes = ctypes.sizeof(arr)
    ort_dispatch.call(api, "CreateTensorWithDataAsOrtValue", mem_info,
                      ctypes.cast(arr, c_void_p), c_size_t(nbytes),
                      shape, c_size_t(2), _INT64, ctypes.byref(out))


def read_float32_data(api, ort_value, count):
    ptr = c_void_p()
    ort_dispatch.call(api, "GetTensorMutableData", ort_value,
                      ctypes.byref(ptr))
    return list(cast(ptr, POINTER(c_float * count)).contents)
