"""Run a forward pass: 3 int64 inputs → 1 float32 output (last_hidden_state)."""
from ctypes import c_char_p, c_size_t, c_void_p

from embedder._lib import model_io, ort_dispatch


def run(handle, ids, mask, types_):
    tensors = _inputs(handle, ids, mask, types_)
    try:
        out = _invoke(handle, tensors)
    finally:
        _release_inputs(handle, tensors)
    return c_void_p(out[0])


def _inputs(handle, ids, mask, types_):
    return [model_io.int64_tensor(handle.api, vec, handle.mem_info)
            for vec in (ids, mask, types_)]


def _invoke(handle, tensors):
    out = (c_void_p * 1)()
    in_tensors = (c_void_p * len(tensors))(*(t for t, _ in tensors))
    ort_dispatch.call(handle.api, "Run", handle.session, None,
                      _c_names(handle.input_names), in_tensors,
                      c_size_t(len(tensors)),
                      _c_names(handle.output_names[:1]), c_size_t(1), out)
    return out


def _release_inputs(handle, tensors):
    for t, _ in tensors:
        ort_dispatch.call(handle.api, "ReleaseValue", t)


def _c_names(names):
    return (c_char_p * len(names))(*(n.encode("utf-8") for n in names))
