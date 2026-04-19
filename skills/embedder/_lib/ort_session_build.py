"""Session bring-up helpers: env, session options, session, allocator, mem."""
from ctypes import byref, c_void_p

from embedder._lib import model_io, ort_dispatch, ort_session_opts

_CPU_ARENA_ALLOCATOR = 0
_MEM_TYPE_DEFAULT = 0


def env_and_opts(api):
    env = c_void_p()
    ort_dispatch.call(api, "CreateEnv", 2, b"claude-mem-embedder", byref(env))
    return env, ort_session_opts.build_options(api)


def create_session(api, env, opts, model_path):
    session = c_void_p()
    ort_dispatch.call(api, "CreateSession", env,
                      model_io.encode_model_path(model_path),
                      opts, byref(session))
    return session


def alloc_and_mem(api):
    allocator = c_void_p()
    ort_dispatch.call(api, "GetAllocatorWithDefaultOptions", byref(allocator))
    return allocator, _cpu_mem_info(api)


def _cpu_mem_info(api):
    mem = c_void_p()
    ort_dispatch.call(api, "CreateCpuMemoryInfo", _CPU_ARENA_ALLOCATOR,
                      _MEM_TYPE_DEFAULT, byref(mem))
    return mem
