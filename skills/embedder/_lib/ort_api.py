"""Load ORT dylib, resolve OrtApi vtable via CFUNCTYPE. Version-gate >=1.17.

Per 1.24.4 onnxruntime_c_api.h lines 910-927, OrtApiBase declares GetApi
at slot 0 and GetVersionString at slot 1 (NOT the reverse — plan was
wrong). Code follows the header.
"""
from ctypes import CDLL, CFUNCTYPE, POINTER, c_char_p, c_uint32, c_void_p, cast

from embedder._lib.paths import EmbedderUnavailable

_ORT_API_VERSION = 16  # works on ORT >= 1.17 per append-only ABI rules


def load_api(dylib_path):
    lib = CDLL(str(dylib_path))
    get_base = CFUNCTYPE(POINTER(c_void_p))(("OrtGetApiBase", lib))
    base = get_base()
    get_api = cast(base[0], CFUNCTYPE(c_void_p, c_uint32))
    get_version = cast(base[1], CFUNCTYPE(c_char_p))
    _version_gate(get_version())
    return _resolve_api(get_api)


def _resolve_api(get_api):
    api_ptr = get_api(_ORT_API_VERSION)
    if not api_ptr:
        raise EmbedderUnavailable(
            f"OrtGetApiBase().GetApi({_ORT_API_VERSION}) returned NULL")
    return c_void_p(api_ptr)


def _version_gate(version_bytes):
    parts = (version_bytes or b"0.0.0").decode("ascii").split(".")
    major, minor = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
    if major < 1 or (major == 1 and minor < 17):
        raise EmbedderUnavailable(
            f"ORT {version_bytes!r} too old; need >= 1.17")
