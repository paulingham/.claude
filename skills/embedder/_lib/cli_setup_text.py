"""Per-OS setup instructions for the embedder CLI.

Kept separate from cli_actions.py so the constants don't push that module
past the 50-line shape limit. setup_text() dispatches by platform.system().
"""
import platform

_MAC_SETUP = (
    "Embedder setup (macOS):\n"
    "  brew install onnxruntime\n"
    "  export ORT_DYLIB_PATH=/opt/homebrew/lib/libonnxruntime.dylib\n"
    "  export BGE_MODEL_PATH=~/.claude/models/bge-small-en-v1.5/model.onnx\n"
    "  skills/embedder/download-model.sh\n")

_LINUX_SETUP = (
    "Embedder setup (Linux):\n"
    "  sudo apt-get install -y libonnxruntime-dev\n"
    "  export ORT_DYLIB_PATH=/usr/lib/x86_64-linux-gnu/libonnxruntime.so\n"
    "  export BGE_MODEL_PATH=~/.claude/models/bge-small-en-v1.5/model.onnx\n"
    "  skills/embedder/download-model.sh\n")

WINDOWS_MSG = ("Windows is not supported. Use WSL (Windows Subsystem for"
               " Linux) and re-run setup from inside the Linux shell.\n")

# Back-compat alias — legacy readers may import SETUP_TEXT.
SETUP_TEXT = _MAC_SETUP


def setup_text():
    return _LINUX_SETUP if platform.system() == "Linux" else _MAC_SETUP
