"""Index-based dispatch into the OrtApi vtable via ctypes.cast."""
from ctypes import POINTER, c_void_p, cast

from embedder._lib.ort_api_table import IDX, SIG
from embedder._lib.paths import EmbedderRuntimeError


def call(api_ptr, name, *args):
    fn = _resolve(api_ptr, name)
    result = fn(*args)
    if name == "GetErrorCode":
        return int(result)
    if name.startswith("Release"):
        return None
    if result:
        _raise_from_status(api_ptr, result)
    return None


def _resolve(api_ptr, name):
    vtable = cast(api_ptr, POINTER(c_void_p))
    return cast(vtable[IDX[name]], SIG[name])


def _raise_from_status(api_ptr, status_ptr):
    msg = _message(api_ptr, status_ptr) or "<no message>"
    _release_status(api_ptr, status_ptr)
    raise EmbedderRuntimeError(f"ORT: {msg}")


def _message(api_ptr, status_ptr):
    fn = _resolve(api_ptr, "GetErrorMessage")
    raw = fn(c_void_p(status_ptr))
    return raw.decode("utf-8", errors="replace") if raw else ""


def _release_status(api_ptr, status_ptr):
    fn = _resolve(api_ptr, "ReleaseStatus")
    fn(c_void_p(status_ptr))
