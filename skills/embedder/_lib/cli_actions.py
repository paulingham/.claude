"""CLI action helpers: probe, doctor, status, setup."""
import sys

from embedder import status as status_mod

SETUP_TEXT = (
    "Embedder setup:\n"
    "  export ORT_DYLIB_PATH=/opt/homebrew/lib/libonnxruntime.dylib\n"
    "  export BGE_MODEL_PATH=~/.claude/models/bge-small-en-v1.5/model.onnx\n"
    "  skills/embedder/download-model.sh\n")


def probe():
    from embedder.embedder import get_embedder
    get_embedder().encode("probe")
    return {"ok": True, "model": "bge-small-en-v1.5", "dim": 384}


def doctor():
    try:
        payload = probe()
    except Exception as exc:
        sys.stdout.write(f"embedder doctor: error — {exc}\n")
        return 1
    sys.stdout.write(f"embedder doctor: ok ({payload['model']})\n")
    return 0


def status():
    try:
        status_mod.write(probe())
    except Exception as exc:
        status_mod.write({"ok": False, "error": str(exc)})
    return 0


def setup():
    sys.stdout.write(SETUP_TEXT)
    return 0
