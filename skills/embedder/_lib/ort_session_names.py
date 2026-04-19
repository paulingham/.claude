"""Enumerate input/output tensor names. Each name copied to str + freed."""
from ctypes import byref, c_char_p, c_size_t, c_void_p

from embedder._lib import ort_dispatch


def read_input_names(api, session, allocator):
    return _read_names(api, session, allocator,
                       "SessionGetInputCount", "SessionGetInputName")


def read_output_names(api, session, allocator):
    return _read_names(api, session, allocator,
                       "SessionGetOutputCount", "SessionGetOutputName")


def _read_names(api, session, allocator, count_op, name_op):
    count = c_size_t()
    ort_dispatch.call(api, count_op, session, byref(count))
    return tuple(_read_one(api, session, allocator, name_op, i)
                 for i in range(count.value))


def _read_one(api, session, allocator, name_op, index):
    raw = c_char_p()
    ort_dispatch.call(api, name_op, session, c_size_t(index),
                      allocator, byref(raw))
    return _take_and_free(api, allocator, raw)


def _take_and_free(api, allocator, raw):
    text = raw.value.decode("utf-8") if raw.value else ""
    ort_dispatch.call(api, "AllocatorFree", allocator, raw)
    return text
