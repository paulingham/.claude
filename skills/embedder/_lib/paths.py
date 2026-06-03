"""Resolve ORT_DYLIB_PATH and BGE_MODEL_PATH; raise EmbedderUnavailable."""
import os
import sys
from pathlib import Path

_LIB_DIR = str(Path(__file__).parent)
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)
from harness_paths import harness_root  # noqa: E402

_DEFAULT_MODEL = harness_root() / "models" / "bge-small-en-v1.5" / "model.onnx"


class EmbedderUnavailable(RuntimeError):
    """Raised when ORT dylib or model file cannot be resolved."""


class EmbedderRuntimeError(RuntimeError):
    """Raised when ORT loaded but inference failed (corrupt model, etc.)."""


def resolve_dylib():
    return _resolve_env("ORT_DYLIB_PATH", default=None)


def resolve_model():
    return _resolve_env("BGE_MODEL_PATH", default=_DEFAULT_MODEL)


def _resolve_env(name, default):
    raw = os.environ.get(name) or (str(default) if default else "")
    if not raw:
        raise EmbedderUnavailable(f"{name} not set")
    return _require_exists(Path(raw), name)


def _require_exists(path, name):
    if not path.exists():
        raise EmbedderUnavailable(f"{name} points to missing file: {path}")
    return path
