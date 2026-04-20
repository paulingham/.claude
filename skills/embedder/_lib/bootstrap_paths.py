"""S9: path helpers for embedder bootstrap.

Probes both homebrew prefixes (Apple Silicon + Intel) per plan risk row.
"""
from pathlib import Path

_BREW_PREFIXES = ("/opt/homebrew/lib", "/usr/local/lib")


def dylib_path():
    for prefix in _BREW_PREFIXES:
        candidate = Path(prefix) / "libonnxruntime.dylib"
        if candidate.exists():
            return candidate
    return Path(_BREW_PREFIXES[0]) / "libonnxruntime.dylib"


def model_path():
    return (Path.home() / ".claude" / "models"
            / "bge-small-en-v1.5" / "model.onnx")


def download_script():
    return Path(__file__).resolve().parents[1] / "download-model.sh"
