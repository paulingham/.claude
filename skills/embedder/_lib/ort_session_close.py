"""Per-field release helper. Swallows individual failures; caller aggregates."""
from embedder._lib import ort_dispatch


def try_release(handle, field, op):
    try:
        _release_one(handle, field, op)
    except Exception as exc:
        return exc


def _release_one(handle, field, op):
    ptr = getattr(handle, field, None)
    if ptr and ptr.value:
        ort_dispatch.call(handle.api, op, ptr)
        setattr(handle, field, None)
