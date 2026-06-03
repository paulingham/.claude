"""S10: model-file-presence gate for capture-time embedding.

Mirrors env-resolution semantics in embedder/_lib/paths.py::_resolve_env
(name + default-if-unset + exists check). Drift between the two is
guarded by tests/test_embed_presence_coeq.py — keep them in sync.

Stdlib-only by design: import from embed_gate stays zero-cost on the
miss path (no embedder.* modules loaded).
"""
import functools
import os
import sys
from pathlib import Path

_LIB_DIR = str(Path(__file__).parent)
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)
from harness_paths import harness_root  # noqa: E402

_DEFAULT_MODEL = harness_root() / "models" / "bge-small-en-v1.5" / "model.onnx"

_WARN_MSG = ("embedder model not bootstrapped; semantic recall disabled."
             " Run /project-setup to enable.\n")


def models_present():
    return _path_ok("ORT_DYLIB_PATH", None) \
        and _path_ok("BGE_MODEL_PATH", _DEFAULT_MODEL)


@functools.lru_cache(maxsize=1)
def warn_missing_once():
    sys.stderr.write(_WARN_MSG)


def _reset_warn_cache():
    warn_missing_once.cache_clear()


def _path_ok(name, default):
    raw = os.environ.get(name) or (str(default) if default else "")
    return bool(raw) and Path(raw).exists()
