"""Build OrtSessionOptions: 8 intra-op threads (M-series P-core count),
all graph opts."""
from ctypes import byref, c_void_p

from embedder._lib import ort_dispatch

_GRAPH_OPT_ALL = 99  # ORT_ENABLE_ALL per onnxruntime_c_api.h
_INTRA_OP_THREADS = 8  # tuned for M-series; 4x speedup vs single-threaded


def build_options(api):
    opts = c_void_p()
    ort_dispatch.call(api, "CreateSessionOptions", byref(opts))
    _apply_defaults(api, opts)
    return opts


def _apply_defaults(api, opts):
    ort_dispatch.call(api, "SetIntraOpNumThreads", opts, _INTRA_OP_THREADS)
    ort_dispatch.call(api, "SetSessionGraphOptimizationLevel",
                      opts, _GRAPH_OPT_ALL)
