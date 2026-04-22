"""Path helpers for embedder bootstrap — OS-aware ORT resolution.

dylib_path() honours ORT_DYLIB_PATH first, then probes OS-dispatched
candidates (Homebrew on macOS, Debian multiarch on Linux). Returns a
Path; non-existent fallback target allows callers to distinguish "must
install" from "already resolved" via Path.exists().
"""
import os
import platform
from pathlib import Path

_MAC_CANDIDATES = ("/opt/homebrew/lib/libonnxruntime.dylib",
                   "/usr/local/lib/libonnxruntime.dylib")
_LINUX_CANDIDATES = ("/usr/lib/x86_64-linux-gnu/libonnxruntime.so",
                     "/usr/lib/libonnxruntime.so")


def dylib_path():
    override = os.environ.get("ORT_DYLIB_PATH")
    if override and Path(override).exists():
        return Path(override)
    return _first_existing(_candidates()) or Path(_candidates()[0])


def _candidates():
    return _LINUX_CANDIDATES if platform.system() == "Linux" else _MAC_CANDIDATES


def _first_existing(paths):
    for p in paths:
        if Path(p).exists():
            return Path(p)
    return None


def model_path():
    return (Path.home() / ".claude" / "models"
            / "bge-small-en-v1.5" / "model.onnx")


def download_script():
    return Path(__file__).resolve().parents[1] / "download-model.sh"
