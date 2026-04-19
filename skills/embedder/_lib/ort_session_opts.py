"""Build OrtSessionOptions: single thread, all graph opts."""
from ctypes import byref, c_void_p

from embedder._lib import ort_dispatch

_GRAPH_OPT_ALL = 99  # ORT_ENABLE_ALL per onnxruntime_c_api.h


def build_options(api):
    opts = c_void_p()
    ort_dispatch.call(api, "CreateSessionOptions", byref(opts))
    _apply_defaults(api, opts)
    return opts


def _apply_defaults(api, opts):
    ort_dispatch.call(api, "SetIntraOpNumThreads", opts, 1)
    ort_dispatch.call(api, "SetSessionGraphOptimizationLevel",
                      opts, _GRAPH_OPT_ALL)
