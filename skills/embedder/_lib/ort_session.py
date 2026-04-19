"""Session orchestrator: build handle, close handle. See RELEASE_ORDER."""
import types
from ctypes import byref, c_void_p

from embedder._lib import (model_io, ort_dispatch, ort_session_build,
                           ort_session_names, ort_session_opts)

RELEASE_ORDER = (
    ("session", "ReleaseSession"),
    ("session_options", "ReleaseSessionOptions"),
    ("mem_info", "ReleaseMemoryInfo"),
    ("env", "ReleaseEnv"),
)


def build(api, model_path):
    env, opts = ort_session_build.env_and_opts(api)
    session = ort_session_build.create_session(api, env, opts, model_path)
    allocator, mem = ort_session_build.alloc_and_mem(api)
    names = _read_names(api, session, allocator)
    return _handle(api, env, opts, session, allocator, mem, names)


def _read_names(api, session, allocator):
    ins = ort_session_names.read_input_names(api, session, allocator)
    outs = ort_session_names.read_output_names(api, session, allocator)
    return ins, outs


def _handle(api, env, opts, sess, alloc, mem, names):
    return types.SimpleNamespace(
        api=api, env=env, session_options=opts, session=sess,
        allocator=alloc, mem_info=mem,
        input_names=names[0], output_names=names[1])


def close(handle):
    for field, op in RELEASE_ORDER:
        _release_one(handle, field, op)


def _release_one(handle, field, op):
    ptr = getattr(handle, field, None)
    if ptr and ptr.value:
        ort_dispatch.call(handle.api, op, ptr)
        setattr(handle, field, None)
