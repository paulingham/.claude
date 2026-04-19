"""IDX + SIG for the 28 OrtApi entries S5.1 uses. Indices from fixture."""
import json
from ctypes import (CFUNCTYPE, POINTER, c_char_p, c_int, c_int64, c_size_t,
                    c_uint32, c_void_p)
from pathlib import Path

_FIXTURE = Path(__file__).resolve().parents[2] / "embedder" / "tests" \
    / "fixtures" / "ort_api_indices.json"
IDX = json.loads(_FIXTURE.read_text())["idx"]

_S = CFUNCTYPE(c_void_p, c_void_p)  # shortcut: OrtStatus* fn(OrtXxx*)
_SS = CFUNCTYPE(c_void_p, c_void_p, c_void_p)
_V = CFUNCTYPE(None, c_void_p)      # Release* — returns void

SIG = {
    "GetErrorCode":   CFUNCTYPE(c_int, c_void_p),
    "GetErrorMessage": CFUNCTYPE(c_char_p, c_void_p),
    "CreateEnv":      CFUNCTYPE(c_void_p, c_int, c_char_p, POINTER(c_void_p)),
    "CreateSession":  CFUNCTYPE(c_void_p, c_void_p, c_char_p, c_void_p,
                                POINTER(c_void_p)),
    "Run":            CFUNCTYPE(c_void_p, c_void_p, c_void_p,
                                POINTER(c_char_p), POINTER(c_void_p), c_size_t,
                                POINTER(c_char_p), c_size_t, POINTER(c_void_p)),
    "CreateSessionOptions": CFUNCTYPE(c_void_p, POINTER(c_void_p)),
    "SetSessionGraphOptimizationLevel": CFUNCTYPE(c_void_p, c_void_p, c_int),
    "SetIntraOpNumThreads": CFUNCTYPE(c_void_p, c_void_p, c_int),
    "SessionGetInputCount":  CFUNCTYPE(c_void_p, c_void_p, POINTER(c_size_t)),
    "SessionGetOutputCount": CFUNCTYPE(c_void_p, c_void_p, POINTER(c_size_t)),
    "SessionGetInputName":   CFUNCTYPE(c_void_p, c_void_p, c_size_t, c_void_p,
                                       POINTER(c_char_p)),
    "SessionGetOutputName":  CFUNCTYPE(c_void_p, c_void_p, c_size_t, c_void_p,
                                       POINTER(c_char_p)),
    "CreateTensorWithDataAsOrtValue": CFUNCTYPE(c_void_p, c_void_p, c_void_p,
                                                c_size_t, POINTER(c_int64),
                                                c_size_t, c_int,
                                                POINTER(c_void_p)),
    "GetTensorMutableData": CFUNCTYPE(c_void_p, c_void_p, POINTER(c_void_p)),
    "GetDimensionsCount": CFUNCTYPE(c_void_p, c_void_p, POINTER(c_size_t)),
    "GetDimensions":      CFUNCTYPE(c_void_p, c_void_p, POINTER(c_int64),
                                    c_size_t),
    "GetTensorTypeAndShape": CFUNCTYPE(c_void_p, c_void_p, POINTER(c_void_p)),
    "CreateCpuMemoryInfo": CFUNCTYPE(c_void_p, c_int, c_int, POINTER(c_void_p)),
    "AllocatorFree":       _SS,
    "GetAllocatorWithDefaultOptions": CFUNCTYPE(c_void_p, POINTER(c_void_p)),
    "ReleaseEnv": _V, "ReleaseStatus": _V, "ReleaseMemoryInfo": _V,
    "ReleaseSession": _V, "ReleaseValue": _V, "ReleaseSessionOptions": _V,
    "ReleaseTensorTypeAndShapeInfo": _V,
}
