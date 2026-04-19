"""Embedder facade. Env-dispatches FakeEmbedder vs real ctypes path.

Lazy-imports the ctypes path so the default-off capture flow never pays
for ORT resolution (see Slice 12 / AC9)."""
import os

from embedder._lib import fake

_singleton = None


def get_embedder():
    global _singleton
    if _singleton is None:
        _singleton = _build()
    return _singleton


def _build():
    if os.environ.get("CLAUDE_EMBEDDER") == "fake":
        return fake.FakeEmbedder()
    return _build_real()


def _build_real():
    from embedder._lib import real
    return real.build()


def reset_singleton_for_tests():
    global _singleton
    closer = getattr(_singleton, "close", None)
    if callable(closer):
        closer()
    _singleton = None
