"""Path helpers for embedder bootstrap — OS-aware ORT resolution.

dylib_path() honours ORT_DYLIB_PATH first, then probes OS-dispatched
candidates (Homebrew on macOS, Debian multiarch on Linux). Returns a
Path; non-existent fallback target allows callers to distinguish "must
install" from "already resolved" via Path.exists().
"""
import os
import platform
import sys
from pathlib import Path

_LIB_DIR = str(Path(__file__).parent)
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)
from harness_paths import harness_root  # noqa: E402

from embedder._lib.bootstrap_errors import UnsupportedOSError

_MAC_CANDIDATES = ("/opt/homebrew/lib/libonnxruntime.dylib",
                   "/usr/local/lib/libonnxruntime.dylib")
_LINUX_CANDIDATES = ("/usr/lib/x86_64-linux-gnu/libonnxruntime.so",
                     "/usr/lib/libonnxruntime.so")
_CANDIDATES_BY_OS = {"Darwin": _MAC_CANDIDATES, "Linux": _LINUX_CANDIDATES}


def dylib_path():
    override = os.environ.get("ORT_DYLIB_PATH")
    if override and Path(override).exists():
        return Path(override)
    return _first_existing(_candidates()) or Path(_candidates()[0])


def _candidates():
    system = platform.system()
    if system not in _CANDIDATES_BY_OS:
        raise UnsupportedOSError(
            f"Unsupported OS: {system}. Supported: macOS, Linux.")
    return _CANDIDATES_BY_OS[system]


def _first_existing(paths):
    for p in paths:
        if Path(p).exists():
            return Path(p)
    return None


def model_path():
    return harness_root() / "models" / "bge-small-en-v1.5" / "model.onnx"


def download_script():
    return Path(__file__).resolve().parents[1] / "download-model.sh"
