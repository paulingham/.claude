"""CLI action helpers: probe, doctor, status, setup."""
import sys

from embedder import status as status_mod

SETUP_TEXT = (
    "Embedder setup:\n"
    "  export ORT_DYLIB_PATH=/opt/homebrew/lib/libonnxruntime.dylib\n"
    "  export BGE_MODEL_PATH=~/.claude/models/bge-small-en-v1.5/model.onnx\n"
    "  skills/embedder/download-model.sh\n")

_WINDOWS_MSG = ("Windows is not supported. Use WSL (Windows Subsystem for"
                " Linux) and re-run setup from inside the Linux shell.\n")


def probe():
    from embedder.embedder import get_embedder
    get_embedder().encode("probe")
    return {"ok": True, "model": "bge-small-en-v1.5", "dim": 384}


def doctor():
    from embedder._lib import doctor as doctor_mod
    sys.stdout.write(doctor_mod.report())
    return 0


def status():
    try:
        status_mod.write(probe())
    except Exception as exc:
        status_mod.write({"ok": False, "error": str(exc)})
    return 0


def setup():
    if sys.platform == "win32":
        sys.stdout.write(_WINDOWS_MSG)
        return 1
    sys.stdout.write(SETUP_TEXT)
    return 0
